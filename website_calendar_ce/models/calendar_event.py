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


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    def _default_access_token(self):
        return str(uuid.uuid4())

    meeting_url = fields.Char('Meeting url')
    access_token = fields.Char('Access Token', default=_default_access_token, readonly=True)
    booking_type_id = fields.Many2one('calendar.booking.type', 'Online Booking', readonly=True)

    @api.model
    def _get_public_fields(self):
        return super()._get_public_fields() | {'booking_type_id'}

    def _compute_is_highlighted(self):
        super(CalendarEvent, self)._compute_is_highlighted()
        if self.env.context.get('active_model') == 'calendar.booking.type':
            booking_type_id = self.env.context.get('active_id')
            for event in self:
                if event.booking_type_id.id == booking_type_id:
                    event.is_highlighted = True

    def _init_column(self, column_name):
        """ Initialize the value of the column for existing rows.
        """
        if column_name != 'access_token':
            super(CalendarEvent, self)._init_column(column_name)

    def _generate_access_token(self):
        for event in self:
            event.access_token = self._default_access_token()
