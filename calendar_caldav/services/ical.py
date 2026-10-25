"""iTIP parsing and generation (RFC 5546).

Odoo core can *send* an invitation but never *receive* one: nothing in
``calendar/`` parses an incoming ``METHOD:REQUEST``.  That is why an
invitation from Outlook or Google lands in a mailbox and dies there.

This module is the missing half.  It reads the iTIP method out of a
``text/calendar`` payload and turns the ``VEVENT`` into values Odoo can
store, and it builds the ``REPLY`` that goes back to the organiser.

Two ``.ics`` generators now exist in the system:

* ``calendar.event._get_ics_file()`` (Odoo core, ``vobject``) — sends an
  invitation out.  It sets neither ``METHOD`` nor ``UID``, so it cannot
  carry an iTIP message; it is left untouched.
* ``build_itip_reply()`` (here, ``icalendar``) — the iTIP half.

Keep them apart on purpose.  If you change one, check the other.
"""

import logging
from datetime import datetime, timezone

from icalendar import Calendar, Event, vCalAddress

from odoo import fields

_logger = logging.getLogger(__name__)

#: iTIP methods we act on.  DECLINECOUNTER is not implemented: Odoo has no
#: concept of a counter-proposal, so answering one would mean inventing it.
SUPPORTED_METHODS = ('REQUEST', 'REPLY', 'CANCEL', 'COUNTER')

#: iTIP PARTSTAT values, mapped to ``calendar.attendee.state``.
PARTSTAT_TO_STATE = {
    'NEEDS-ACTION': 'needsAction',
    'TENTATIVE': 'tentative',
    'DECLINED': 'declined',
    'ACCEPTED': 'accepted',
    'DELEGATED': 'needsAction',
}

STATE_TO_PARTSTAT = {
    'needsAction': 'NEEDS-ACTION',
    'tentative': 'TENTATIVE',
    'declined': 'DECLINED',
    'accepted': 'ACCEPTED',
}


class ItipError(Exception):
    """The payload is not something we can act on."""


def _as_list(value):
    """``icalendar`` returns a single component or a list, depending on count."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _email_of(address):
    """Strip the ``mailto:`` scheme and any surrounding whitespace."""
    if address is None:
        return ''
    text = str(address).strip()
    if text.lower().startswith('mailto:'):
        text = text[7:]
    return text.strip()


def _param(component, name):
    """Read a parameter that ``icalendar`` may have stored as list or str."""
    value = component.params.get(name)
    if isinstance(value, list):
        return value[0] if value else ''
    return value or ''


def _to_naive_utc(value):
    """Odoo stores naive UTC datetimes; iCalendar may hand us aware ones."""
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_itip(data):
    """Parse an iTIP payload into a plain dict.

    :param data: ``text/calendar`` bytes or str.
    :returns: ``{'method', 'uid', 'sequence', 'organizer', 'attendees',
                 'event', 'recurrence_id'}`` where ``event`` holds the
                 VEVENT values Odoo understands.
    :raises ItipError: when the payload carries no usable VEVENT.
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    try:
        calendar = Calendar.from_ical(data)
    except Exception as exc:  # icalendar raises a variety of parser errors
        raise ItipError('not a calendar: %s' % exc)

    method = str(calendar.get('method') or '').upper()
    vevents = _as_list(calendar.walk('VEVENT'))
    if not vevents:
        raise ItipError('no VEVENT in payload')

    vevent = vevents[0]

    uid = str(vevent.get('uid') or '').strip()
    if not uid:
        # Without a UID a PUT cannot be idempotent and a REPLY cannot be
        # matched to its event, so refuse rather than invent one.
        raise ItipError('VEVENT has no UID')

    organizer = None
    organizer_line = vevent.get('organizer')
    if organizer_line is not None:
        organizer = {
            'email': _email_of(organizer_line),
            'name': _param(organizer_line, 'CN'),
        }

    attendees = []
    for line in _as_list(vevent.get('attendee')):
        email = _email_of(line)
        if not email:
            continue
        attendees.append({
            'email': email,
            'name': _param(line, 'CN'),
            'partstat': (_param(line, 'PARTSTAT') or 'NEEDS-ACTION').upper(),
            'rsvp': str(_param(line, 'RSVP')).upper() == 'TRUE',
            'role': (_param(line, 'ROLE') or 'REQ-PARTICIPANT').upper(),
        })

    values = {}
    if vevent.get('summary') is not None:
        values['name'] = str(vevent.get('summary'))
    if vevent.get('dtstart') is not None:
        values['start'] = _to_naive_utc(vevent.get('dtstart').dt)
    if vevent.get('dtend') is not None:
        values['stop'] = _to_naive_utc(vevent.get('dtend').dt)
    if vevent.get('location') is not None:
        values['location'] = str(vevent.get('location'))
    if vevent.get('description') is not None:
        values['description'] = str(vevent.get('description'))
    if vevent.get('url') is not None:
        values['videocall_location'] = str(vevent.get('url'))

    klass = vevent.get('class')
    if klass is not None:
        privacy = {'PRIVATE': 'private', 'CONFIDENTIAL': 'confidential'}.get(
            str(klass).upper())
        if privacy:
            values['privacy'] = privacy

    recurrence_id = vevent.get('recurrence-id')
    if recurrence_id is not None:
        # A RECURRENCE-ID names the instance being changed. Without it a
        # change to one occurrence of a series would rewrite the series.
        values['_recurrence_id'] = _to_naive_utc(recurrence_id.dt)

    sequence = vevent.get('sequence')
    try:
        sequence = int(sequence) if sequence is not None else 0
    except (TypeError, ValueError):
        sequence = 0

    return {
        'method': method,
        'uid': uid,
        'sequence': sequence,
        'organizer': organizer,
        'attendees': attendees,
        'event': values,
        'recurrence_id': values.pop('_recurrence_id', None),
    }


def build_itip_reply(event, attendee, partstat=None):
    """Build a ``METHOD:REPLY`` payload for one attendee.

    This is the message Odoo has never been able to send.  It goes back to
    the organiser so their calendar shows whether we accepted or declined.

    :param event: ``calendar.event`` record.
    :param attendee: ``calendar.attendee`` record (the one replying).
    :param partstat: override; defaults to the attendee's state.
    """
    calendar = Calendar()
    calendar.add('prodid', '-//Odoo//calendar_caldav//EN')
    calendar.add('version', '2.0')
    calendar.add('method', 'REPLY')

    vevent = Event()
    vevent.add('uid', event.uuid or 'event-%s@odoo' % event.id)
    vevent.add('sequence', _sequence_of(event))
    vevent.add('dtstamp', fields.Datetime.now())

    if event.start:
        vevent.add('dtstart', event.start)
    if event.stop:
        vevent.add('dtend', event.stop)

    organizer_email = _organizer_email(event)
    if organizer_email:
        organizer = vCalAddress('mailto:%s' % organizer_email)
        if event.user_id and event.user_id.name:
            organizer.params['CN'] = event.user_id.name
        vevent.add('organizer', organizer, encode=0)

    address = vCalAddress('mailto:%s' % (attendee.email or ''))
    if attendee.common_name:
        address.params['CN'] = attendee.common_name
    address.params['PARTSTAT'] = partstat or STATE_TO_PARTSTAT.get(
        attendee.state, 'NEEDS-ACTION')
    vevent.add('attendee', address, encode=0)

    calendar.add_component(vevent)
    return calendar.to_ical()


def build_itip_cancel(event):
    """Build a ``METHOD:CANCEL`` payload for an event we organise."""
    calendar = Calendar()
    calendar.add('prodid', '-//Odoo//calendar_caldav//EN')
    calendar.add('version', '2.0')
    calendar.add('method', 'CANCEL')

    vevent = Event()
    vevent.add('uid', event.uuid or 'event-%s@odoo' % event.id)
    vevent.add('sequence', _sequence_of(event))
    vevent.add('dtstamp', fields.Datetime.now())
    if event.start:
        vevent.add('dtstart', event.start)
    if event.stop:
        vevent.add('dtend', event.stop)
    vevent.add('summary', event.name or '')

    organizer_email = _organizer_email(event)
    if organizer_email:
        organizer = vCalAddress('mailto:%s' % organizer_email)
        if event.user_id and event.user_id.name:
            organizer.params['CN'] = event.user_id.name
        vevent.add('organizer', organizer, encode=0)

    calendar.add_component(vevent)
    return calendar.to_ical()


def _organizer_email(event):
    """The organiser's address, or '' when the event has none.

    ``imip_organizer`` wins: an event received from Outlook keeps Odoo's
    default ``user_id`` (OdooBot) as its owner, and replying to OdooBot
    instead of the real organiser means the organiser never learns the
    answer.
    """
    if event.imip_organizer:
        return event.imip_organizer
    if event.user_id:
        return event.user_id.partner_id.email or event.user_id.email or ''
    return ''


def _sequence_of(event):
    """Our outgoing SEQUENCE.

    Odoo has no sequence column, so derive it from the revision counter we
    keep on the event.  A REPLY always carries the sequence of the REQUEST
    it answers, which is what the organiser matches on.
    """
    return getattr(event, 'itip_sequence', 0) or 0


def build_itip_counter(event, attendee, proposed_start, proposed_stop):
    """Build a ``METHOD:COUNTER`` payload proposing another time.

    RFC 5546 §3.2.3: an attendee who cannot make the proposed time answers
    with a counter-proposal instead of a plain decline. The organiser then
    accepts or declines it.
    """
    calendar = Calendar()
    calendar.add('prodid', '-//Odoo//calendar_caldav//EN')
    calendar.add('version', '2.0')
    calendar.add('method', 'COUNTER')

    vevent = Event()
    vevent.add('uid', event.uuid or 'event-%s@odoo' % event.id)
    vevent.add('sequence', _sequence_of(event))
    vevent.add('dtstamp', fields.Datetime.now())
    vevent.add('dtstart', proposed_start)
    vevent.add('dtend', proposed_stop)
    if event.name:
        vevent.add('summary', event.name)

    organizer_email = _organizer_email(event)
    if organizer_email:
        organizer = vCalAddress('mailto:%s' % organizer_email)
        if event.user_id and event.user_id.name:
            organizer.params['CN'] = event.user_id.name
        vevent.add('organizer', organizer, encode=0)

    address = vCalAddress('mailto:%s' % (attendee.email or ''))
    if attendee.common_name:
        address.params['CN'] = attendee.common_name
    address.params['PARTSTAT'] = 'TENTATIVE'
    vevent.add('attendee', address, encode=0)

    calendar.add_component(vevent)
    return calendar.to_ical()
