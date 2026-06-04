from html import escape

import pytz
from icalendar import Calendar, Event, vCalAddress
from odoo import fields
from odoo.http import request
from datetime import datetime


def _add_attendees(event, ical_event):
    for attendee in event.attendee_ids:
        addr = vCalAddress(f"mailto:{attendee.email or ''}")
        if attendee.common_name:
            addr.params["CN"] = attendee.common_name
        else:
            addr.params["CN"] = attendee.partner_id.name or ""
        partstat_map = {
            "needsAction": "NEEDS-ACTION",
            "tentative": "TENTATIVE",
            "declined": "DECLINED",
            "accepted": "ACCEPTED",
        }
        addr.params["PARTSTAT"] = partstat_map.get(attendee.state, "NEEDS-ACTION")
        addr.params["ROLE"] = "REQ-PARTICIPANT"
        addr.params["CUTYPE"] = "INDIVIDUAL"
        ical_event.add("attendee", addr, encode=0)


def _add_attachments(event, ical_event, base_url):
    attachments = request.env["ir.attachment"].search([
        ("res_model", "=", "calendar.event"),
        ("res_id", "=", event.id),
    ])
    for att in attachments:
        if att.mimetype and not att.mimetype.startswith("text/"):
            ical_event.add("attach", f"{escape(base_url)}/web/content/{att.id}/datas")


def _build_ical_event(event, base_url=None):
    ical_event = Event()
    ical_event.add("uid", event.uuid or f"event-{event.id}@odoo")
    ical_event.add("summary", event.name)
    ical_event.add("dtstart", event.start)
    ical_event.add("dtend", event.stop)

    description_parts = []
    if event.description:
        description_parts.append(event.description)
    if event.videocall_location:
        description_parts.append(f"Video call: {event.videocall_location}")
    if description_parts:
        ical_event.add("description", "\n\n".join(description_parts))

    ical_event.add("last-modified", event.write_date)
    ical_event.add("dtstamp", datetime.utcnow())
    ical_event.add("created", event.create_date or datetime.utcnow())

    if event.location:
        ical_event.add("location", event.location)
    if event.videocall_location:
        ical_event.add("url", event.videocall_location)
        ical_event.add("X-VIDEOCALL-URL", event.videocall_location)
    if event.categ_ids:
        ical_event.add("categories", [cat.name for cat in event.categ_ids])

    _add_attendees(event, ical_event)
    if base_url:
        _add_attachments(event, ical_event, base_url)

    if event.recurrency and event.recurrence_id and event.recurrence_id.rrule:
        ical_event.add('rrule', event.recurrence_id.rrule)

    return ical_event


def odoo_event_to_icalendar(event, base_url=None):
    cal = Calendar()
    cal.add("prodid", "-//Odoo Calendar//EN")
    cal.add("version", "2.0")
    cal.add_component(_build_ical_event(event, base_url))
    return cal

def icalendar_to_odoo_event(ical_str, event=None):
    cal = Calendar.from_ical(ical_str)
    ical_event = cal.walk("VEVENT")[0]

    start_dt = ical_event.get("dtstart").dt
    if isinstance(start_dt, datetime) and start_dt.tzinfo:
        start_dt = start_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    stop_dt = ical_event.get("dtend").dt
    if isinstance(stop_dt, datetime) and stop_dt.tzinfo:
        stop_dt = stop_dt.astimezone(pytz.UTC).replace(tzinfo=None)

    desc = str(ical_event.get("description", ""))
    event_data = {
        "name": str(ical_event.get("summary")),
        "start": start_dt,
        "stop": stop_dt,
        "description": desc,
    }

    location = ical_event.get("location")
    if location:
        event_data["location"] = str(location)

    url = ical_event.get("url")
    if url:
        event_data["videocall_location"] = str(url)

    cat_val = ical_event.get("categories")
    if cat_val:
        cat_names = [str(c) for c in (cat_val.cats if hasattr(cat_val, 'cats') else [cat_val]) if str(c)]
        if cat_names:
            Type = request.env["calendar.event.type"]
            ids = []
            for name in cat_names:
                tag = Type.search([("name", "=", name)], limit=1)
                if not tag:
                    tag = Type.create({"name": name})
                ids.append(tag.id)
            event_data["categ_ids"] = [(6, 0, ids)]

    attendees = ical_event.get("attendee")
    if attendees:
        if not isinstance(attendees, list):
            attendees = [attendees]
        partner_ids = []
        for att in attendees:
            mailto = str(att)
            if mailto.startswith("mailto:"):
                email = mailto[7:]
            else:
                email = mailto
            partner = request.env["res.partner"].search([("email", "=", email)], limit=1)
            if not partner:
                cn = att.params.get("CN", email)
                partner = request.env["res.partner"].create({
                    "name": str(cn) if cn else email,
                    "email": email,
                })
            partner_ids.append(partner.id)
        event_data["partner_ids"] = [(6, 0, partner_ids)]

    if "rrule" in ical_event:
        event_data["recurrency"] = str(ical_event["rrule"].to_ical()).split("=")[1]

    if event:
        event.write(event_data)
        return event
    else:
        return request.env["calendar.event"].create(event_data)

def odoo_events_to_icalendar(events, cal_name=None, base_url=None):
    cal = Calendar()
    cal.add("prodid", "-//Odoo Calendar//EN")
    cal.add("version", "2.0")
    if cal_name:
        cal.add("X-WR-CALNAME", cal_name)
    for event in events:
        cal.add_component(_build_ical_event(event, base_url))
    return cal