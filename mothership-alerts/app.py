import json
import os
from pathlib import Path

from modal import App, Cron, Image, Secret, Volume


app = App("mothership-ticket-alerts")
my_image = Image.debian_slim(python_version="3.10").pip_install(
    "beautifulsoup4", "requests", "twilio", "python-slugify"
)
volume = Volume.from_name("mothership", create_if_missing=True)

VOLUME_MOUNT_PATH = Path("/vol")
EVENT_LIST_PATH = VOLUME_MOUNT_PATH / "event_list.json"


@app.function(
    image=my_image,
    volumes={VOLUME_MOUNT_PATH: volume},
    secrets=[Secret.from_name("twilio")],
    schedule=Cron("*/10 * * * *"),
)
def check_for_updates():
    from datetime import date, datetime

    import requests
    from bs4 import BeautifulSoup
    from slugify import slugify  # type: ignore
    from twilio.rest import Client  # type: ignore

    def info_to_event_id(info):
        date_str = info["date"]
        try:
            dt = datetime.strptime(date_str, "%A, %b %d %Y")
        except ValueError:
            today = date.today()
            month_day = datetime.strptime(date_str, "%A, %b %d").replace(year=today.year)
            year = month_day.year if month_day.date() >= today else month_day.year + 1
            dt = datetime.strptime(f"{date_str} {year}", "%A, %b %d %Y")
        start_time = info["time"].split("-")[0].strip()
        start_obj = datetime.strptime(start_time, "%I:%M %p").time()
        return f"{slugify(info['show_title'])}-{dt.strftime('%Y%m%d')}-{start_obj.strftime('%H%M')}"

    url = "https://comedymothership.com/shows"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    content_container = soup.find("div", class_="content container")
    show_items = content_container.find_all("li")

    data = {}
    for item in show_items:
        try:
            date_str = item.find("div", class_="h6").get_text(strip=True)
        except Exception:
            continue
        show_title = item.find("h3").get_text(strip=True)
        li_items = item.find_all("li")
        time = li_items[0].text
        room = li_items[1].text
        info = dict(show_title=show_title, date=date_str, time=time, room=room)
        event_id = info_to_event_id(info)
        data[event_id] = info

    if not EVENT_LIST_PATH.exists():
        EVENT_LIST_PATH.write_text(json.dumps(data, indent=2))
        volume.commit()
        return

    old_data = json.loads(EVENT_LIST_PATH.read_text())
    new_events = {k: v for k, v in data.items() if k not in old_data}
    EVENT_LIST_PATH.write_text(json.dumps(data, indent=2))
    volume.commit()

    if new_events:
        client = Client(os.environ["TWILIO_SID"], os.environ["TWILIO_AUTH"])
        for event in new_events.values():
            client.messages.create(
                body=f"New event at Mothership! {event['show_title']} — {event['date']} at {event['time']} in {event['room']}",
                from_=os.environ["TWILIO_PHONE"],
                to=os.environ["TO_PHONE"],
            )
    else:
        print("No new events found")
        # ########################################################################################
        # # For debugging, you can delete some events from the event list to test the alert works
        # # For debugging, you can delete some events from the event list to test the alert works
        # ########################################################################################
        # Delete a few existing events for testing purposes
        # for event_id in list(old_data)[:3]:
        #     del old_data[event_id]
        # EVENT_LIST_PATH.write_text(json.dumps(old_data, indent=2))
        # volume.commit()
