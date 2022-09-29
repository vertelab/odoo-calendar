# -*- coding: utf-8 -*-
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#


import uuid
from odoo import api, fields, models
from odoo.addons.calendar.models.calendar_event import Meeting as MeetingOriginal

import logging

_logger = logging.getLogger(__name__)


class Attendee(models.Model):
    """ Calendar Attendee Information """
    _inherit = 'calendar.attendee'

    public_user = fields.Boolean(string='Is public user', default=False)


class Meeting(models.Model):
    _inherit = "calendar.event"

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [  # Else bug with quick_create when we are filter on an other user
            dict(vals, user_id=self.env.user.id) if not 'user_id' in vals else vals
            for vals in vals_list
        ]

        public_partner = False

        for values in vals_list:
            if values.get('public_partner'):
                public_partner = values.pop('public_partner')

            # created from calendar: try to create an activity on the related record
            if not values.get('activity_ids'):
                defaults = self.default_get(['activity_ids', 'res_model_id', 'res_id', 'user_id'])
                res_model_id = values.get('res_model_id', defaults.get('res_model_id'))
                res_id = values.get('res_id', defaults.get('res_id'))
                user_id = values.get('user_id', defaults.get('user_id'))
                if not defaults.get('activity_ids') and res_model_id and res_id:
                    if hasattr(self.env[self.env['ir.model'].sudo().browse(res_model_id).model], 'activity_ids'):
                        meeting_activity_type = self.env['mail.activity.type'].search([('category', '=', 'meeting')],
                                                                                      limit=1)
                        if meeting_activity_type:
                            activity_vals = {
                                'res_model_id': res_model_id,
                                'res_id': res_id,
                                'activity_type_id': meeting_activity_type.id,
                            }
                            if user_id:
                                activity_vals['user_id'] = user_id
                            values['activity_ids'] = [(0, 0, activity_vals)]

        # Add commands to create attendees from partners (if present) if no attendee command
        # is already given (coming from Google event for example).
        vals_list = [
            dict(vals, attendee_ids=self._attendees_values(vals['partner_ids']))
            if 'partner_ids' in vals and not vals.get('attendee_ids')
            else vals
            for vals in vals_list
        ]
        recurrence_fields = self._get_recurrent_fields()
        recurring_vals = [vals for vals in vals_list if vals.get('recurrency')]
        other_vals = [vals for vals in vals_list if not vals.get('recurrency')]
        events = super(MeetingOriginal, self).create(other_vals)

        for vals in recurring_vals:
            vals['follow_recurrence'] = True
        recurring_events = super(MeetingOriginal, self).create(recurring_vals)
        events += recurring_events

        for event, vals in zip(recurring_events, recurring_vals):
            recurrence_values = {field: vals.pop(field) for field in recurrence_fields if field in vals}
            if vals.get('recurrency'):
                detached_events = event._apply_recurrence_values(recurrence_values)
                detached_events.active = False
        if public_partner:
            events.filtered(lambda event: event.start > fields.Datetime.now()).attendee_ids.filtered(
                lambda attendee: attendee.partner_id.id == public_partner.id)._send_mail_to_attendees(
                'website_calendar_ce.calendar_template_meeting_invitation_public')
            events.filtered(lambda event: event.start > fields.Datetime.now()).attendee_ids.filtered(
                lambda attendee: attendee.partner_id.id != public_partner.id)._send_mail_to_attendees(
                'calendar.calendar_template_meeting_invitation')
        else:
            events.filtered(lambda event: event.start > fields.Datetime.now()).attendee_ids._send_mail_to_attendees(
                'calendar.calendar_template_meeting_invitation')
        events._sync_activities(fields={f for vals in vals_list for f in vals.keys()})

        # Notify attendees if there is an alarm on the created event, as it might have changed their
        # next event notification
        if not self._context.get('dont_notify'):
            for event in events:
                if len(event.alarm_ids) > 0:
                    self.env['calendar.alarm_manager']._notify_next_alarm(event.partner_ids.ids)
        return events

    def _default_access_token(self):
        return str(uuid.uuid4())

    meeting_url = fields.Char('Meeting url')
    access_token = fields.Char('Access Token', default=_default_access_token, readonly=True)
    booking_type_id = fields.Many2one('calendar.booking.type', 'Online Booking', readonly=True)

    @api.model
    def _get_public_fields(self):
        return super()._get_public_fields() | {'booking_type_id'}

    def _compute_is_highlighted(self):
        super(Meeting, self)._compute_is_highlighted()
        if self.env.context.get('active_model') == 'calendar.booking.type':
            booking_type_id = self.env.context.get('active_id')
            for event in self:
                if event.booking_type_id.id == booking_type_id:
                    event.is_highlighted = True

    def _init_column(self, column_name):
        """ Initialize the value of the column for existing rows.
        """
        if column_name != 'access_token':
            super(Meeting, self)._init_column(column_name)

    def _generate_access_token(self):
        for event in self:
            event.access_token = self._default_access_token()
