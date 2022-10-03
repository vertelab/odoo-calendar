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


from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
from babel.dates import format_datetime, format_date

from werkzeug.urls import url_encode

from odoo import http, _, fields
from odoo.http import request
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools.misc import get_lang
import uuid
import logging

_logger = logging.getLogger(__name__)


class WebsiteCalendar(http.Controller):

    @http.route([
        '/website/calendar/products',
        '/website/calendar/products/<model("calendar.booking.type"):booking_type>/'], type='http', auth="public", website=True)
    def calendar_booking_product_choice(self, booking_type=None, product_id=None, **kwargs):
        if not booking_type:
            country_code = request.session.geoip and request.session.geoip.get('country_code')
            if country_code:
                suggested_booking_types = request.env['calendar.booking.type'].search([
                    '|', ('country_ids', '=', False),
                    ('country_ids.code', 'in', [country_code])])
            else:
                suggested_booking_types = request.env['calendar.booking.type'].search([])
            if not suggested_booking_types:
                return request.render("website_calendar_ce.setup", {})
            booking_type = suggested_booking_types[0]
        else:
            suggested_booking_types = booking_type
        suggested_products = []
        if product_id and int(product_id) in booking_type.sudo().product_ids.ids:
            suggested_products = request.env['product.product'].sudo().browse(int(product_id)).name_get()
        elif booking_type.assignation_method == 'chosen':
            suggested_products = booking_type.sudo().employee_ids.name_get()
        return request.render("website_calendar_product_resource.index", {
            'booking_type': booking_type,
            'suggested_booking_types': suggested_booking_types,
            'selected_product_id': product_id and int(product_id),
            'suggested_products': suggested_products,
        })
