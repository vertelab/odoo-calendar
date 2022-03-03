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

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
from babel.dates import format_datetime, format_date

from werkzeug.urls import url_encode

from odoo import http, _, fields
from odoo.http import request
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools.misc import get_lang


_logger = logging.getLogger(__name__)


class WebsiteCalendar(http.Controller):

    @http.route(['/website/calendar/booking/slots'], type='json', auth="public", website=True)
    def _get_calendar_booking_slot(self, booking_type=None, employee_id=None, timezone=None, failed=False, **kwargs):
        BookingType = request.env['calendar.booking.type'].sudo().browse(int(booking_type)) if booking_type else None
        request.session['timezone'] = timezone or BookingType.booking_tz
        Employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None
        Slots = BookingType.sudo()._get_booking_slots(request.session['timezone'], Employee)
        return {
            'booking_type': BookingType.name,
            'timezone': request.session['timezone'],
            'failed': failed,
            'slots': Slots,
        }
