# -*- coding: utf-8 -*-

import base64

from odoo import models

# States that mean "the attendee responded" and should be distributed to the
# other attendees.
RESPONSE_STATES = ('accepted', 'declined', 'tentative')


class CalendarEvent(models.Model):
    _description = 'Extended Calendar Event Notifications'
    _inherit = "calendar.event"

    def _ics_attachment(self, method='REQUEST'):
        """Build the iTIP payload for this event and return it as an
        ``ir.attachment`` ready to be passed in ``email_values``.

        The payload is produced by ``calendar.event._get_ics_file()``; when
        ``calendar_ics_invitations`` is installed that is the Outlook/Teams
        compatible override, otherwise core's payload is used as-is.
        """
        self.ensure_one()
        try:
            ics_files = self._get_ics_file(method=method)
        except TypeError:
            # Core's _get_ics_file() takes no method argument.
            ics_files = self._get_ics_file()
        ics_file = ics_files.get(self.id)
        if not ics_file:
            return self.env['ir.attachment']
        return self.env['ir.attachment'].with_context(no_document=True).create({
            'datas': base64.b64encode(ics_file),
            'description': 'invitation.ics',
            'mimetype': 'text/calendar',
            'res_id': 0,
            'res_model': 'mail.compose.message',
            'name': 'invitation.ics',
        })

    def unlink(self):
        # Get concerned attendees to notify them if there is an alarm on the unlinked events,
        # as it might have changed their next event notification
        events = self.filtered_domain([('alarm_ids', '!=', False)])
        partner_ids = events.mapped('partner_ids').ids

        template = self.env.ref('extended_calendar_notifications.calendar_event_cancelled')
        for event in self:
            # Bump the sequence so the cancellation is newer than the last
            # invitation the recipient received, then build the CANCEL payload
            # while the event still exists.
            event.with_context(skip_ics_bump=True).write(
                {'ics_sequence': event.ics_sequence + 1})
            attachment = event._ics_attachment(method='CANCEL')
            for attendee in event.attendee_ids:
                template.send_mail(
                    attendee.id,
                    email_layout_xmlid='mail.mail_notification_light',
                    force_send=True,
                    email_values={'attachment_ids': [(6, 0, attachment.ids)]},
                )

        result = super().unlink()

        # Notify the concerned attendees (must be done after removing the events)
        self.env['calendar.alarm_manager']._notify_next_alarm(partner_ids)

        return result


class CalendarAttendee(models.Model):
    _inherit = 'calendar.attendee'

    def write(self, values):
        previous_states = {attendee.id: attendee.state for attendee in self}
        result = super().write(values)
        if 'state' in values and not self.env.context.get('skip_response_update'):
            for attendee in self:
                if (previous_states.get(attendee.id) != attendee.state
                        and attendee.state in RESPONSE_STATES):
                    attendee._distribute_response()
        return result

    def _distribute_response(self):
        """Send the other attendees an iTIP update carrying this attendee's new
        PARTSTAT. The responder and the organizer are excluded: the responder
        already knows, and the organizer is notified through the event chatter
        message posted by ``do_accept``/``do_decline``/``do_tentative``."""
        self.ensure_one()
        event = self.event_id
        if not event or event.user_id.partner_id == self.partner_id:
            return
        template = self.env.ref(
            'extended_calendar_notifications.calendar_template_meeting_response',
            raise_if_not_found=False)
        if not template:
            return

        event.with_context(skip_ics_bump=True).write(
            {'ics_sequence': event.ics_sequence + 1})
        attachment = event._ics_attachment(method='REQUEST')

        recipients = event.attendee_ids.filtered(
            lambda att: att.email
            and att != self
            and att.partner_id != event.user_id.partner_id)
        for recipient in recipients:
            template.with_context(skip_response_update=True).send_mail(
                recipient.id,
                email_layout_xmlid='mail.mail_notification_light',
                force_send=True,
                email_values={'attachment_ids': [(6, 0, attachment.ids)]},
            )
