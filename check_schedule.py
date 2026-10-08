import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from icalendar import Calendar


ICAL_URL = (
    "https://www.ijshockey.nl/competities/ical"
    "?divisionId=21753&teamId=32402"
)

STATE_FILE = "schedule.json"


def download_calendar():
    request = urllib.request.Request(
        ICAL_URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_calendar(data):
    calendar = Calendar.from_ical(data)

    games = []

    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", ""))
        location = str(component.get("LOCATION", ""))

        dtstart = component.get("DTSTART")
        if not dtstart:
            continue

        dtstart = dtstart.dt

        if isinstance(dtstart, datetime):
            date_time = dtstart.isoformat()
        else:
            date_time = dtstart.isoformat()

        games.append({
            "uid": uid,
            "summary": summary,
            "location": location,
            "datetime": date_time
        })

    games.sort(key=lambda x: x["uid"])

    return games


def load_previous():
    if not os.path.exists(STATE_FILE):
        return None

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_current(games):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=2)


def send_email(changes):
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    body = "Er is een wijziging gevonden in het wedstrijdschema van The Outlaws.\n\n"

    for change in changes:
        body += "========================================\n"

        if change["type"] == "added":
            body += "NIEUWE WEDSTRIJD\n\n"
            body += f"Wedstrijd: {change['new']['summary']}\n"
            body += f"Datum/tijd: {change['new']['datetime']}\n"
            body += f"Locatie: {change['new']['location']}\n"

        elif change["type"] == "removed":
            body += "WEDSTRIJD VERWIJDERD\n\n"
            body += f"Wedstrijd: {change['old']['summary']}\n"
            body += f"Datum/tijd: {change['old']['datetime']}\n"
            body += f"Locatie: {change['old']['location']}\n"

        elif change["type"] == "changed":
            body += "WEDSTRIJD GEWIJZIGD\n\n"
            body += f"Wedstrijd: {change['new']['summary']}\n\n"

            if change["old"]["datetime"] != change["new"]["datetime"]:
                body += (
                    f"Datum/tijd:\n"
                    f"  Oud: {change['old']['datetime']}\n"
                    f"  Nieuw: {change['new']['datetime']}\n\n"
                )

            if change["old"]["location"] != change["new"]["location"]:
                body += (
                    f"Locatie:\n"
                    f"  Oud: {change['old']['location']}\n"
                    f"  Nieuw: {change['new']['location']}\n\n"
                )

            if change["old"]["summary"] != change["new"]["summary"]:
                body += (
                    f"Wedstrijd:\n"
                    f"  Oud: {change['old']['summary']}\n"
                    f"  Nieuw: {change['new']['summary']}\n"
                )

        body += "\n"

    body += (
        "\nDit bericht is automatisch verstuurd.\n"
        "Bron: IJshockey Nederland\n"
    )

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Subject"] = "🏒 Wijziging wedstrijdschema The Outlaws"

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def compare(old, new):
    if old is None:
        return []

    old_by_uid = {game["uid"]: game for game in old}
    new_by_uid = {game["uid"]: game for game in new}

    changes = []

    # Nieuwe wedstrijden
    for uid in new_by_uid:
        if uid not in old_by_uid:
            changes.append({
                "type": "added",
                "new": new_by_uid[uid]
            })

    # Verwijderde wedstrijden
    for uid in old_by_uid:
        if uid not in new_by_uid:
            changes.append({
                "type": "removed",
                "old": old_by_uid[uid]
            })

    # Gewijzigde wedstrijden
    for uid in old_by_uid:
        if uid not in new_by_uid:
            continue

        old_game = old_by_uid[uid]
        new_game = new_by_uid[uid]

        if old_game != new_game:
            changes.append({
                "type": "changed",
                "old": old_game,
                "new": new_game
            })

    return changes


def main():
    print("Wedstrijdschema ophalen...")

    data = download_calendar()

    current = parse_calendar(data)
    previous = load_previous()

    print(f"{len(current)} wedstrijden gevonden.")

    changes = compare(previous, current)

    if changes:
        print(f"{len(changes)} wijziging(en) gevonden.")

        send_email(changes)

    else:
        print("Geen wijzigingen.")

    save_current(current)


if __name__ == "__main__":
    main()
