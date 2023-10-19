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

from odoo import http, _, fields
from odoo.http import request
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.addons.website_calendar_ce.controllers.main import WebsiteCalendar
from odoo.tools.misc import get_lang
import uuid
import logging

_logger = logging.getLogger(__name__)


class WebsiteCalendarExtended(WebsiteCalendar):

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/info'], type='http', auth="public",
                website=True)
    def calendar_booking_form(self, booking_type, employee_id, start_date, end_date=None, description=None, title=None,
                              **kwargs):
        partner_data = {}
        if request.env.user.partner_id != request.env.ref('base.public_partner'):
            partner_data = request.env.user.partner_id.read(fields=['name', 'mobile', 'country_id', 'email'])[0]
        start_day_name = format_datetime(datetime.strptime(start_date, dtf), 'EEE', locale=get_lang(request.env).code)
        start_date_formatted = format_datetime(datetime.strptime(start_date, dtf), locale=get_lang(request.env).code)

        vals = {
            'partner_data': partner_data,
            'booking_type': booking_type,
            'start_datetime': start_date,
            'start_datetime_locale': start_day_name + ' ' + start_date_formatted,
            'start_datetime_str': start_date,
            'employee_id': employee_id,
            'countries': request.env['res.country'].search([]),
            'description': description if description else _(
                "Fill your personal information in the form below, and confirm the booking. We'll send an invite to "
                "your email address"),
            'title': title if title else _("Book meeting"),
        }
        if end_date:
            end_day_name = format_datetime(datetime.strptime(end_date, dtf), 'EEE', locale=get_lang(request.env).code)
            end_date_formatted = format_datetime(datetime.strptime(end_date, dtf), locale=get_lang(request.env).code)
            vals.update({
                'end_datetime': end_date,
                'end_datetime_locale': end_day_name + ' ' + end_date_formatted,
                'end_datetime_str': end_date,
            })

        print(employee_id)
        employee = request.env['hr.employee'].sudo().browse(int(employee_id))
        if employee.user_id and employee.user_id.partner_id:
            if not employee.user_id.partner_id.calendar_verify_availability(fields.Datetime.from_string(start_date),
                                                                            fields.Datetime.from_string(end_date)):
                return request.redirect('/website/calendar/%s/booking?failed=employee' % booking_type.id)

        if end_date and (datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S") > datetime.strptime(end_date, "%Y-%m-%d "
                                                                                                          "%H:%M:%S")):
            return request.redirect('/website/calendar/%s/booking?failed=datetime' % booking_type.id)

        return request.render("website_calendar_ce.booking_form", vals)

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/submit'], type='http', auth="public",
                website=True, methods=["POST"])
    def calendar_booking_submit(self, booking_type, start_datetime_str, employee_id, name, phone, email,
                                end_datetime_str=None, country_id=False, comment=False, company=False,
                                description=False, title=_("Book meeting"), **kwargs):
        timezone = request.session['timezone']
        tz_session = pytz.timezone(timezone)
        date_start = tz_session.localize(fields.Datetime.from_string(start_datetime_str)).astimezone(pytz.utc)
        if end_datetime_str:
            date_end = tz_session.localize(fields.Datetime.from_string(end_datetime_str)).astimezone(pytz.utc)
        else:
            date_end = date_start + relativedelta(hours=booking_type.booking_duration)

        # check availability of the employee again (in case someone else booked while the client was entering the form)
        hr_employee_id = request.env['hr.employee'].sudo().browse(int(employee_id))
        if hr_employee_id.user_id and hr_employee_id.user_id.partner_id:
            if not hr_employee_id.user_id.partner_id.calendar_verify_availability(date_start, date_end):
                return request.redirect('/website/calendar/%s/booking?failed=employee' % booking_type.id)

        country_id = int(country_id) if country_id else None
        country_name = country_id and request.env['res.country'].browse(country_id).name or ''
        partner = request.env['res.partner'].sudo().search([('email', '=like', email)], limit=1)
        if partner:
            if not partner.calendar_verify_availability(date_start, date_end):
                return request.redirect('/website/calendar/%s/booking?failed=partner' % booking_type.id)
            if not partner.mobile or len(partner.mobile) <= 5 and len(phone) > 5:
                partner.write({'mobile': phone})
            if not partner.country_id:
                partner.country_id = country_id
        else:
            partner = partner.create({
                'name': name,
                'country_id': country_id,
                'mobile': phone,
                'email': email,
            })

        record_description = (_('Country: %s') + '\n\n' +
                              _('Mobile: %s') + '\n\n' +
                              _('Email: %s') + '\n\n') % (country_name, phone, email)
        for question in booking_type.question_ids:
            key = 'question_' + str(question.id)
            if question.question_type == 'checkbox':
                answers = question.answer_ids.filtered(lambda x: (key + '_answer_' + str(x.id)) in kwargs)
                record_description += question.name + ': ' + ', '.join(answers.mapped('name')) + '\n'
            elif kwargs.get(key):
                if question.question_type == 'text':
                    record_description += '\n* ' + question.name + ' *\n' + kwargs.get(key, False) + '\n\n'
                else:
                    record_description += question.name + ': ' + kwargs.get(key) + '\n\n'
        if company:
            record_description += _("Company: ") + company
        if comment:
            record_description += _("\n\nComment: ") + comment
        if description:
            record_description += _("\n\nDescription: ") + description
        if title:
            record_description += _("\n\nTitle: ") + title

        categ_id = request.env.ref('website_calendar_ce.calendar_event_type_data_online_booking')
        alarm_ids = booking_type.reminder_ids and [(6, 0, booking_type.reminder_ids.ids)] or []
        partner_ids = list(set([hr_employee_id.user_id.partner_id.id] + [partner.id]))
        public_partner = False
        if not partner.user_id:
            public_partner = partner
        data = {
            'state': 'open',
            'name': _('%s with %s') % (booking_type.name, name),
            # FIXME master
            # we override here start_date(time) value because they are not properly
            # recomputed due to ugly overrides in event.calendar (reccurrencies suck!)
            #     (fixing them in stable is a pita as it requires a good rewrite of the
            #      calendar engine)
            'start_date': date_start.strftime(dtf),
            'start': date_start.strftime(dtf),
            'stop': date_end.strftime(dtf),
            'allday': False,
            'duration': booking_type.booking_duration,
            'description': record_description,
            'alarm_ids': alarm_ids,
            'location': f"https://{booking_type.meeting_base_url}/{str(uuid.uuid1())}",
            'partner_ids': [(4, pid, False) for pid in partner_ids],
            'public_partner': public_partner,
            'categ_ids': [(4, categ_id.id, False)],
            'booking_type_id': booking_type.id,
            'user_id': hr_employee_id.user_id.id,
            'meeting_url': f"https://{booking_type.meeting_base_url}/{str(uuid.uuid1())}"
        }
        if end_datetime_str:
            data.update({
                'allday': True,
                'stop_date': date_end.strftime(dtf)
            })
        event = self._create_event(request, hr_employee_id, data)
        event.attendee_ids.filtered(lambda attendee: attendee.partner_id.id == partner.id).write({'public_user': True})
        event.attendee_ids.write({'state': 'accepted'})
        return request.redirect('/website/calendar/view/' + event.access_token + '?message=new' + '&title=' + title)

