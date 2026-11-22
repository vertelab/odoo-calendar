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


from werkzeug.utils import redirect

from odoo import http, SUPERUSER_ID
from odoo import registry as registry_get
from odoo.api import Environment
from odoo.http import request

from odoo.addons.calendar.controllers.main import CalendarController


class WebsiteCalendarController(CalendarController):

    def view(self, db, token, action, id, view='calendar', **kwargs):
        """ Redirect the user to the website page of the calendar.event, only if it is an booking """
        super(WebsiteCalendarController, self).view(db, token, action, id, view='calendar', **kwargs)
        registry = registry_get(db)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            attendee = env['calendar.attendee'].search([('access_token', '=', token), ('event_id', '=', int(id))])
            if attendee:
                request.session['timezone'] = attendee.partner_id.tz
                if not attendee.event_id.access_token:
                    attendee.event_id._generate_access_token()
                return redirect('/website/calendar/view/' + str(attendee.event_id.access_token))
            else:
                return request.render("website_calendar_ce.booking_invalid", {})
