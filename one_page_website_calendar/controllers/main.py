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
import base64
import json
import pytz

from datetime import datetime
from psycopg2 import IntegrityError
from werkzeug.exceptions import BadRequest

from odoo import http, SUPERUSER_ID, _
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.ir_qweb_fields import nl2br

_logger = logging.getLogger(__name__)


class WebsiteCalendar(http.Controller):

    @http.route(['/website/calendar/booking/slots'], type='json', auth="public", website=True)
    def _get_calendar_booking_slot(self, booking_type=None, employee_id=None, timezone=None, month=0, failed=False,
                                   **kwargs):
        BookingType = request.env['calendar.booking.type'].sudo().browse(int(booking_type)) if booking_type else None
        request.session['timezone'] = timezone or BookingType.booking_tz
        Employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None
        Slots = BookingType.sudo()._get_advanced_booking_slots(request.session['timezone'], int(month), Employee)
        return {
            'booking_type': BookingType.name,
            'booking_type_id': BookingType.id,
            'employee_id': Employee.id,
            'timezone': request.session['timezone'],
            'failed': failed,
            'slots': Slots,
        }

    @http.route(['/website/calendar/slot/info'], type='json', auth="public", website=True)
    def _calendar_slot_booking_form(self, booking_type, employee_id, date_time, **kwargs):
        partner_data = {}
        if request.env.user.partner_id != request.env.ref('base.public_partner'):
            partner_data = request.env.user.partner_id.read(fields=['name', 'mobile', 'country_id', 'email'])[0]
        day_name = format_datetime(datetime.strptime(date_time, dtf), 'EEE', locale=get_lang(request.env).code)
        date_formatted = format_datetime(datetime.strptime(date_time, dtf), locale=get_lang(request.env).code)
        BookingType = request.env['calendar.booking.type'].sudo().browse(int(booking_type)) if booking_type else None
        values = {
            'partner_data': partner_data,
            'booking_type': BookingType.id,
            'booking_type_name': BookingType.name,
            'datetime': date_time,
            'datetime_locale': day_name + ' ' + date_formatted,
            'datetime_str': date_time,
            'employee_id': employee_id,
            'countries': [
                {'id': rec.id, 'phone_code': rec.phone_code, 'name': rec.name}
                for rec in request.env['res.country'].search([])
            ],
            'question_ids': [
                {
                    'id': question.id,
                    'question_type': question.question_type,
                    'name': question.name,
                    'placeholder': question.placeholder,
                    'answer_ids': [
                        {'id': answer.id, 'name': answer.name}
                        for answer in question.answer_ids
                    ],
                }
                for question in BookingType.question_ids
            ],
            'csrf_token': request.csrf_token()
        }
        return values
