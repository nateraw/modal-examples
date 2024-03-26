import json
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from modal import Cron, Image, Secret, Stub, Volume
from modal.runner import deploy_stub


stub = Stub()
my_image = Image.debian_slim().pip_install("beautifulsoup4", "requests")
volume = Volume.from_name("mothership", create_if_missing=True)

VOLUME_MOUNT_PATH = Path("/vol")
EVENT_LIST_PATH = VOLUME_MOUNT_PATH / "event_list.json"
CARRIER_EXT_MAP = {
    "att": "@txt.att.net",
    "tmobile": "@tmomail.net",
    "verizon": "@vtext.com",
}


@stub.function(
    image=my_image,
    volumes={VOLUME_MOUNT_PATH: volume},
    secrets=[Secret.from_name("textme")],
    # Run every 5 minutes, all day erry day
    # That's 288 requests / day.
    schedule=Cron("*/10 * * * *"),
)
def check_for_updates():
    import requests
    from bs4 import BeautifulSoup

    url = "https://comedymothership.com/shows"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    content_container = soup.find("div", class_="content container")
    show_items = content_container.find_all("li")
    data = {}
    for item in show_items:
        if item.find("a"):
            url = item.find("a")["href"]
            date = item.find("div", class_="h6").text
            time = item.select_one(".EventCard_detailsWrapper__s0qUH li:first-child").text
            event_id = url.split("/")[-1]
            data[event_id] = dict(url=url, date=date, time=time)

    if not EVENT_LIST_PATH.exists():
        print("No event list found in volume to compare against. Saving current events and exiting.")
        EVENT_LIST_PATH.write_text(json.dumps(data, indent=2))
        volume.commit()
        return

    old_data = json.loads(EVENT_LIST_PATH.read_text())
    new_events = {k: v for k, v in data.items() if k not in old_data}
    EVENT_LIST_PATH.write_text(json.dumps(data, indent=2))
    volume.commit()
    if new_events:
        print("New events found:")
        print(json.dumps(new_events, indent=2))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(os.environ["GOOGLE_EMAIL"], os.environ["GOOGLE_AUTH_PASSWORD"])
        event_ids = list(new_events)
        for i in range(0, len(event_ids), 3):
            msg_text = "\n".join(event_ids[i : i + 2])
            # TODO - I was using urls in the msgs, but that was causing issue with format of sent message.
            # I think this perhaps could be because of some spam filtering on Google's side.
            # So, instead, I'm just sending the event ids for now.
            # I moved to use MIMEText instead of string, as I thought that would fix it, but it didn't.
            msg = MIMEText(msg_text)
            msg["Subject"] = "New Events at Mothership!"
            msg["From"] = os.environ["GOOGLE_EMAIL"]
            msg["To"] = os.environ["PHONE_NUMBER"] + CARRIER_EXT_MAP[os.environ["PHONE_CARRIER"]]
            server.send_message(msg)
            print(f"Message sent!\n{'-' * 80}\n{msg_text}\n{'-' * 80}")
    else:
        print("No new events found")

        # For debugging, you can delete some events from the event list to test the alert works
        # # Delete a few existing events for testing purposes
        # for event_id in list(old_data)[:6]:
        #     del old_data[event_id]

        # EVENT_LIST_PATH.write_text(json.dumps(old_data, indent=2))
        # volume.commit()


if __name__ == "__main__":
    deploy_stub(stub, name="mothership-ticket-alerts")
