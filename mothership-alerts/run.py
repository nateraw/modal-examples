import json
import os
from pathlib import Path

from modal import App, Cron, Image, Secret, Volume
from modal.runner import deploy_app


app = App()
my_image = Image.debian_slim().pip_install("beautifulsoup4", "requests", "twilio")
volume = Volume.from_name("mothership", create_if_missing=True)

VOLUME_MOUNT_PATH = Path("/vol")
EVENT_LIST_PATH = VOLUME_MOUNT_PATH / "event_list.json"


@app.function(
    image=my_image,
    volumes={VOLUME_MOUNT_PATH: volume},
    secrets=[Secret.from_name("twilio")],
    # Run every 5 minutes, all day erry day
    # That's 288 requests / day.
    schedule=Cron("*/10 * * * *"),
)
def check_for_updates():
    import requests
    from bs4 import BeautifulSoup
    from twilio.rest import Client

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
        client = Client(os.environ["TWILIO_SID"], os.environ["TWILIO_AUTH"])
        event_ids = list(new_events)
        for event_id in event_ids:
            event = new_events[event_id]
            message = client.messages.create(
                body=f"New event at Mothership! {event['date']} at {event['time']}: {event['url']}",
                from_=os.environ["TWILIO_PHONE"],
                to=os.environ["TO_PHONE"],
            )
            print(f"Message sent!\n{message.sid}")
    else:
        print("No new events found")

        # For debugging, you can delete some events from the event list to test the alert works
        # Delete a few existing events for testing purposes
        # for event_id in list(old_data)[:3]:
        #     del old_data[event_id]

        # EVENT_LIST_PATH.write_text(json.dumps(old_data, indent=2))
        # volume.commit()


if __name__ == "__main__":
    deploy_app(app, name="mothership-ticket-alerts")
