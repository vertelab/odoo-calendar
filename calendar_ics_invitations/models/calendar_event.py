# -*- coding: utf-8 -*-
# Part of calendar_ics_invitations. See LICENSE file for full copyright and licensing details.

import uuid

import pytz
from odoo import api, fields, models

try:
    import vobject
except ImportError:
    vobject = None

# Fields whose change makes the meeting different for the recipient. A write
# touching any of these bumps ``ics_sequence`` so the update is not discarded
# as stale by Outlook/Exchange.
SCHEDULING_FIELDS = {
    'start', 'stop', 'allday', 'name', 'description', 'location',
    'rrule', 'partner_ids', 'privacy', 'show_as',
}

# iTIP PARTSTAT for each ``calendar.attendee.state``. Unknown states fall back
# to NEEDS-ACTION so an unexpected value can never produce a payload a client
# rejects.
PARTSTAT_MAP = {
    'needsAction': 'NEEDS-ACTION',
    'tentative': 'TENTATIVE',
    'declined': 'DECLINED',
    'accepted': 'ACCEPTED',
}

UTC = pytz.timezone('UTC')


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    ics_uid = fields.Char(
        string='ICS UID', readonly=True, copy=False,
        help="Stable, space-free UID used in the iTIP payload. Generated on "
             "first invitation and never changed.")
    ics_sequence = fields.Integer(
        string='ICS Sequence', default=0, readonly=True, copy=False,
        help="iTIP SEQUENCE, incremented on every scheduling-relevant change "
             "so clients accept the update as newer.")

    # ------------------------------------------------------------------
    # Persisted payload state
    # ------------------------------------------------------------------

    def _ensure_ics_uid(self):
        """Return the event's stable UID, generating and persisting it on the
        first call. The generated value is ``<id>-<uuid4>@<dbname>`` and
        contains no whitespace, so it never needs folding or escaping."""
        self.ensure_one()
        if not self.ics_uid:
            uid = '%s-%s@%s' % (self.id, uuid.uuid4(), self.env.cr.dbname)
            # Persisting the UID must not re-enter the sequence bump or the
            # response distribution: the write is bookkeeping, not a change to
            # the meeting.
            self.with_context(skip_ics_bump=True, skip_response_update=True).write(
                {'ics_uid': uid})
        return self.ics_uid

    def write(self, values):
        if (self.env.context.get('skip_ics_bump')
                or not SCHEDULING_FIELDS.intersection(values)):
            return super().write(values)
        # The payload built inside the core write (the invitation/update mail)
        # must already carry the new SEQUENCE, so the bump is applied in the
        # same write as the scheduling change.
        result = True
        for event in self:
            result = super(CalendarEvent, event).write(
                dict(values, ics_sequence=event.ics_sequence + 1))
        return result

    def copy(self, default=None):
        default = dict(default or {})
        # A copy is a new meeting: fresh UID (generated lazily) and sequence 0.
        # Core's copy recreates the attendees, which would otherwise bump the
        # sequence through our write() override, so reset it explicitly.
        default['ics_uid'] = False
        default['ics_sequence'] = 0
        copied = super().copy(default)
        copied.with_context(skip_ics_bump=True).write(
            {'ics_uid': False, 'ics_sequence': 0})
        return copied

    # ------------------------------------------------------------------
    # iTIP payload
    # ------------------------------------------------------------------

    def _get_ics_file(self, method='REQUEST'):
        """Return ``{event_id: bytes}`` iTIP payloads for the events.

        Core's signature is ``_get_ics_file(self)`` and core calls it with no
        arguments, so the extra ``method`` argument is optional and the core
        call site keeps working. The payload is built by core and then re-parsed
        so the Outlook/Exchange/Teams properties can be set without copying
        core's generator.
        """
        result = super()._get_ics_file()
        if not vobject:
            return result

        # Resolve UIDs before building any payload, so persisting one event's
        # UID cannot affect another event's iteration.
        uids = {event.id: event._ensure_ics_uid() for event in self}

        for meeting in self:
            raw = result.get(meeting.id)
            if not raw:
                continue
            calendar = vobject.readOne(raw.decode('utf-8'))
            vevent = calendar.vevent

            calendar.prodid.value = '-//Vertel//Odoo Calendar//EN'
            calendar.add('method').value = method

            vevent.uid.value = uids[meeting.id]
            vevent.add('sequence').value = str(meeting.ics_sequence)
            vevent.add('status').value = (
                'CANCELLED' if method == 'CANCEL' else 'CONFIRMED')
            vevent.add('transp').value = (
                'TRANSPARENT' if meeting.show_as == 'free' else 'OPAQUE')
            vevent.add('class').value = (
                'PRIVATE' if meeting.privacy in ('private', 'confidential')
                else 'PUBLIC')
            vevent.dtstamp.value = fields.Datetime.now().replace(tzinfo=UTC)
            vevent.add('last-modified').value = (
                (meeting.write_date or fields.Datetime.now()).replace(tzinfo=UTC))

            # Core emits bare ATTENDEE lines (uppercase MAILTO:, no parameters)
            # and an ORGANIZER with a hand-escaped CN. Replace both.
            for child in list(vevent.getChildren()):
                if child.name.upper() in ('ATTENDEE', 'ORGANIZER'):
                    vevent.remove(child)

            self._add_organizer(vevent, meeting)
            self._add_attendees(vevent, meeting)

            result[meeting.id] = calendar.serialize().encode('utf-8')

        return result

    def _add_organizer(self, vevent, meeting):
        partner = meeting.partner_id
        if not partner.email:
            return
        organizer = vevent.add('organizer')
        organizer.value = 'mailto:%s' % partner.email.lower()
        if partner.display_name:
            # vobject raises VObjectError on a double quote in a parameter
            # value, so a name containing one cannot be emitted verbatim.
            # Replace it with an apostrophe (as core does) and let vobject
            # handle quoting/escaping of the remaining value (e.g. commas).
            cn = partner.display_name.replace('"', "'")
            organizer.params['CN'] = [cn]

    def _add_attendees(self, vevent, meeting):
        for attendee in meeting.attendee_ids:
            if not attendee.email:
                continue
            line = vevent.add('attendee')
            line.value = 'mailto:%s' % attendee.email.lower()
            line.params['ROLE'] = ['REQ-PARTICIPANT']
            line.params['PARTSTAT'] = [
                PARTSTAT_MAP.get(attendee.state, 'NEEDS-ACTION')]
            line.params['RSVP'] = ['TRUE']
            if attendee.common_name:
                cn = attendee.common_name.replace('"', "'")
                line.params['CN'] = [cn]
