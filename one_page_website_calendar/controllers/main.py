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

from odoo.addons.website_form.controllers.main import WebsiteForm

# class WebsiteFormInherit(WebsiteForm):
#     # Check and insert values from the form on the model <model>
#     @http.route('/website_form/<string:model_name>', type='http', auth="public", methods=['POST'], website=True, csrf=False)
#     def website_form(self, model_name, **kwargs):
#         _logger.warning("#"*999)
#         _logger.warning("website_form")
#         _logger.warning(kwargs)
#         # ~ {'Custom Radioknappar': 'Nej, vi har inte ansökt om hindersprövning', 'name': 'Mitchell Admin', 'E-mail': 'admin@yourcompany.example.com', 'Social Security No': '19900101-0111', 'Street': '215 Vine St', 'Zip': '18503', 'City': 'Scranton', 'project_id': '22', 'employee_id': '3,3,3', 'booking_type_id': '3', 'slot_datetime': '2022-03-07 08:00:00,2022-03-09 08:00:00,2022-03-11 08:00:00,2022-03-14 08:00:00,2022-03-16 08:00:00,2022-03-18 08:00:00', 'datetime_str': '2022-03-18 08:00:00', 'booking_type': '3', 'Example input': 'exempel', 'csrf_token': 'a2c1aa939a92ac536e94348825c38c06c91c4cc5o1677917668'} 
#         # ~ kwargs.pop('employee_id')
#         datetime_str = kwargs.get('datetime_str',False)
#         booking_type = kwargs.get('booking_type',False) 
#         name = kwargs.get('name',False)

#         if kwargs.get('employee_id',False):
#             user_id = request.env['hr.employee'].sudo().browse(int(kwargs.get('employee_id',False).split(',')[0])).user_id
#             _logger.warning(f"{user_id=}")
#             employee_id = user_id.partner_id.id
#             _logger.warning(f"{employee_id=}")

#         partner_form_filler_id = kwargs.get('partner_id',False)
#         if partner_form_filler_id:
#             partner_form_filler_id = kwargs.get('partner_id',False).split(',')[0]
#             _logger.warning(f"{partner_form_filler_id=}")
#         else:
#             # ~ partner_form_filler_id = request.env['res.partner'].search([("name","=",kwargs.get("name"),("social_sec_nr","=",kwargs.get("Social Security No"))])
#             partner_form_filler_id = request.env['res.partner'].search([("name","=",kwargs.get("name")),("social_sec_nr","=",kwargs.get("Social Security No"))])
#             _logger.warning(f"{partner_form_filler_id=}")
        
#         _logger.warning(f"{datetime_str=}")
#         _logger.warning(f"{booking_type=}")
#         # ~ _logger.warning(f"{employee_id=}")
#         _logger.warning(f"{partner_form_filler_id=}")
#         # ~ {'Custom Radioknappar': 'Nej, vi har inte ansökt om hindersprövning', 'name': 'Mitchell Admin', 'E-mail': 'admin@yourcompany.example.com', 'Social Security No': '19900101-0111', 'Street': '215 Vine St', 'Zip': '18503', 'City': 'Scranton', 'project_id': '22', 'employee_id': '20,20,20', 'booking_type_id': '3', 'slot_datetime': '2022-03-07 08:00:00,2022-03-08 15:00:00,2022-03-09 08:00:00,2022-03-10 15:00:00,2022-03-11 08:00:00,2022-03-14 08:00:00,2022-03-15 15:00:00,2022-03-16 08:00:00,2022-03-17 15:00:00,2022-03-18 08:00:00', 'datetime_str': '2022-03-18 08:00:00', 'booking_type': '3', 'Example input': 'exempel', 'csrf_token': 'c18f63a8cdce8a87c7edde4823edbe956e482a8fo1677917507'}
        
#         if datetime_str and booking_type and name and employee_id and partner_form_filler_id:
#             booking_type = int(booking_type)
#             partner_form_filler_id = int(partner_form_filler_id)
            
#             calender_id = request.env['calendar.event'].sudo().create({'name':"VIGSEL %s" % name,"booking_type_id":booking_type,"stop":datetime_str,"start":datetime_str,'duration':60,'partner_ids':[(6, 0, [employee_id,partner_form_filler_id])],'allday':False})
        
#         # ~ yrelated_online_booking_ids
#         _logger.warning(f"1")
#         # Partial CSRF check, only performed when session is authenticated, as there
#         # is no real risk for unauthenticated sessions here. It's a common case for
#         # embedded forms now: SameSite policy rejects the cookies, so the session
#         # is lost, and the CSRF check fails, breaking the post for no good reason.
#         csrf_token = request.params.pop('csrf_token', None)
#         if request.session.uid and not request.validate_csrf(csrf_token):
#             raise BadRequest('Session expired (invalid CSRF token)')

#         # ~ try:
#             # ~ _logger.warning(f"2")
#             # The except clause below should not let what has been done inside
#             # here be committed. It should not either roll back everything in
#             # this controller method. Instead, we use a savepoint to roll back
#             # what has been done inside the try clause.
#             # ~ with request.env.cr.savepoint():
#                 # ~ if request.env['ir.http'].sudo()._verify_request_recaptcha_token('website_form'):
#         # ~ {'name': 'Nils Jonsson', 'E-mail': 'victor.ekstrom@vertel.se', 'Social Security No': '19660202-3118', 'Street': 'PENSÉVÄGEN 2', 'Zip': '57838', 'City': 'Åtvidaberg', 'project_id': '22,22', 'employee_id': '20,20,20', 'booking_type_id': '3', 'slot_datetime': '2022-03-07 08:00:00,2022-03-08 15:00:00,2022-03-09 08:00:00,2022-03-10 15:00:00,2022-03-11 08:00:00,2022-03-14 08:00:00,2022-03-15 15:00:00,2022-03-16 08:00:00,2022-03-17 15:00:00,2022-03-18 08:00:00', 'datetime_str': '2022-03-11 08:00:00', 'booking_type': '3', 'Custom Radioknappar': 'Annan plats', 'Example input': '123', 'csrf_token': '4052b1bee16e5204f1ffe70eb819e385c41a6837o1677922946'}

        
#         # ~ _logger.warning(kwargs['project_id'])
#         # ~ self = self.sudo()
#         _logger.warning(f"{kwargs=}")
#         res = self._handle_website_form(model_name, **kwargs)
#         _logger.warning(res)
#         return res
#             # ~ error = _("Suspicious activity detected by Google reCaptcha.")
#         # ~ except (ValidationError, UserError) as e:
#             # ~ _logger.warning("1"*999)
#             # ~ error = e.args[0]
#             # ~ _logger.warning(error)
#         # ~ return json.dumps({
#             # ~ 'error': error,
#         # ~ })

    