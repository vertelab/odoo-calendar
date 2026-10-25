import base64
import logging
from uuid import uuid4, UUID

from odoo import models, fields, api

from ..services.ical import STATE_TO_PARTSTAT, build_itip_reply

#: ``change_attendee_status`` speaks Odoo state names.
PARTSTAT_FOR_STATE = STATE_TO_PARTSTAT

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    uuid = fields.Char(
        string="UUID",
        readonly=True,
        default=lambda self: str(uuid4()),
        index=True,
    )
    # ── iTIP (RFC 5546) ─────────────────────────────────────────────
    # Odoo has no place to keep the scheduling metadata an invitation
    # carries. Without it a REPLY cannot be matched to its REQUEST and a
    # stale invitation overwrites a newer one.
    imip_organizer = fields.Char(
        string="External Organiser",
        help="Organiser address for events received from another system. "
             "Empty when the organiser is an Odoo user (then user_id).",
    )
    itip_sequence = fields.Integer(
        string="iTIP SEQUENCE",
        default=0,
        help="Revision counter from the last REQUEST we accepted. An "
             "incoming REQUEST with a lower value is ignored.",
    )

    dav_last_modified = fields.Datetime(
        string="Last Modified (DAV)",
        compute="_compute_dav_last_modified",
        store=True,
        index=True,
    )

    @api.depends("write_date")
    def _compute_dav_last_modified(self):
        for event in self:
            event.dav_last_modified = event.write_date

    def _get_or_create_uuid(self):
        if self.uuid:
            return self.uuid
        return str(UUID(int=self.id))

    def init(self):
        self.env.cr.execute(
            "UPDATE calendar_event SET uuid = gen_random_uuid()::text WHERE uuid IS NULL"
        )

    # ── iTIP: send the reply the organiser is waiting for ───────────
    def change_attendee_status(self, status, recurrence_update_setting):
        """Answer an invitation, and tell the organiser we did.

        Odoo's own implementation only writes ``calendar.attendee.state``.
        When the organiser is another system (Outlook, Google, another
        Odoo) that write is invisible to them, so the invitation never
        settles. Send a ``METHOD:REPLY`` back.
        """
        result = super().change_attendee_status(
            status, recurrence_update_setting)
        for event in self:
            attendee = event.attendee_ids.filtered(
                lambda a: a.partner_id == self.env.user.partner_id)
            if attendee:
                event._send_itip_reply(attendee[:1], status)
        return result

    def _send_itip_reply(self, attendee, state):
        """Mail a ``METHOD:REPLY`` to an external organiser.

        Internal organisers are updated through the ORM by Odoo itself, so
        mailing them would only produce noise.
        """
        self.ensure_one()
        if self.user_id:
            return False
        if not self.imip_organizer:
            return False

        payload = build_itip_reply(self, attendee, PARTSTAT_FOR_STATE.get(state))
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'reply.ics',
            'datas': base64.b64encode(payload),
            'mimetype': 'text/calendar',
            'res_model': 'calendar.event',
            'res_id': self.id,
        })
        try:
            self.env['mail.mail'].sudo().create({
                'subject': 'Re: %s' % (self.name or ''),
                'email_to': self.imip_organizer,
                'email_from': attendee.email or self.env.user.email,
                'body_html': '<p>%s</p>' % (
                    attendee.common_name or attendee.partner_id.name or ''),
                'attachment_ids': [(6, 0, attachment.ids)],
                'auto_delete': True,
            }).send()
        except Exception as exc:  # a failed reply must not block the write
            _logger.warning('[iTIP] could not send REPLY for event %s: %s',
                            self.id, exc)
            return False
        return True
