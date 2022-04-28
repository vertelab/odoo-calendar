# -*- coding: utf-8 -*-

from re import template
from odoo import models, fields, api


class Meeting(models.Model):
    _description = 'Extended Calendar Event Notifications'
    _inherit = "calendar.event"

    def unlink(self):
        # Get concerned attendees to notify them if there is an alarm on the unlinked events,
        # as it might have changed their next event notification
        events = self.filtered_domain([('alarm_ids', '!=', False)])
        partner_ids = events.mapped('partner_ids').ids

        template = self.env.ref('extended_calendar_notifications.calendar_event_cancelled')
        for attendee in self.attendee_ids:
            template.send_mail(attendee.id, notif_layout='mail.mail_notification_light', force_send=True)

        result = super().unlink()

        # Notify the concerned attendees (must be done after removing the events)
        self.env['calendar.alarm_manager']._notify_next_alarm(partner_ids)

        return result

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
