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
import random
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
        '/website/calendar/',
        '/website/calendar/<model("calendar.booking.type"):booking_type>/',
    ], type='http', auth="public", website=True)
    def calendar_booking_choice(self, booking_type=None, employee_id=None, message=None, description=None, header=None, **kwargs):
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
        suggested_employees = []
        if employee_id and int(employee_id) in booking_type.sudo().employee_ids.ids:
            suggested_employees = request.env['hr.employee'].sudo().browse(int(employee_id)).name_get()
        elif booking_type.assignation_method == 'chosen':
            suggested_employees = booking_type.sudo().employee_ids.name_get()
        return request.render("website_calendar_ce.index", {
            'booking_type': booking_type,
            'suggested_booking_types': suggested_booking_types,
            'message': message,
            'description': description,
            'header': header,
            'selected_employee_id': employee_id and int(employee_id),
            'suggested_employees': suggested_employees,
        })

    @http.route(['/website/calendar/get_booking_info'], type='json', auth="public", methods=['POST'], website=True)
    def get_booking_info(self, booking_id, prev_emp=False, **kwargs):
        Appt = request.env['calendar.booking.type'].browse(int(booking_id)).sudo()
        result = {
            'message_intro': Appt.message_intro,
            'assignation_method': Appt.assignation_method,
        }
        if result['assignation_method'] == 'chosen':
            selection_template = http.request.env.ref('website_calendar_ce.employee_select')
            data = {
                    'booking_type': Appt,
                    'suggested_employees': Appt.employee_ids.name_get(),
                    'selected_employee_id': prev_emp and int(prev_emp),
                    }
            # TODO: I dislike using private function here, although no other function seems to work
            #       as I need it to work.
            result['employee_selection_html'] = selection_template._render(data)
        return result

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/booking'], type='http', auth="public", website=True)
    def calendar_booking(self, booking_type=None, employee_id=None, timezone=None, failed=False, title=None, description=None, **kwargs):
        request.session['timezone'] = timezone or booking_type.booking_tz
        Employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None
        Slots = booking_type.sudo()._get_booking_slots(request.session['timezone'], Employee)

        
        if  employee_id:
            Employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None
        else:
            Employee = random.choice(booking_type.sudo().employee_ids)
            _logger.warning(f"{employee_id} {Employee}")      
        return request.render("website_calendar_ce.booking", {
            'booking_type': booking_type,
            'timezone': request.session['timezone'],
            'failed': failed,
            'slots': Slots,
            'description': description if description else _("Fill your personal information in the form below, and confirm the booking. We'll send an invite to your email address"),
            'title': title if title else _("Book meeting"),   
        })

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/info'], type='http', auth="public", website=True)
    def calendar_booking_form(self, booking_type, employee_id, date_time, description=None, title=None, **kwargs):
       partner_data = {}
       if request.env.user.partner_id != request.env.ref('base.public_partner'):
            partner_data = request.env.user.partner_id.read(fields=['name', 'mobile', 'country_id', 'email'])[0]
            day_name = format_datetime(datetime.strptime(date_time, dtf), 'EEE', locale=get_lang(request.env).code)
            date_formated = format_datetime(datetime.strptime(date_time, dtf), locale=get_lang(request.env).code)
            
            return request.render("website_calendar_ce.booking_form", {
            'partner_data': partner_data,
            'booking_type': booking_type,
            'datetime': date_time,
            'datetime_locale': day_name + ' ' + date_formated,
            'datetime_str': date_time,
            'employee_id': employee_id,
            'countries': request.env['res.country'].search([]),
            'description': description if description else _("Fill your personal information in the form below, and confirm the booking. We'll send an invite to your email address"),
            'title': title if title else _("Book meeting"),
        })

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/submit'], type='http', auth="public", website=True, methods=["POST"])
    def calendar_booking_submit(self, booking_type, datetime_str, employee_id, name, phone, email, country_id=False, comment=False, company=False, description=False, title=_("Book meeting"), **kwargs):
        timezone = request.session['timezone']
        tz_session = pytz.timezone(timezone)
        date_start = tz_session.localize(fields.Datetime.from_string(datetime_str)).astimezone(pytz.utc)
        date_end = date_start + relativedelta(hours=booking_type.booking_duration)

        # check availability of the employee again (in case someone else booked while the client was entering the form)
        Employee = request.env['hr.employee'].sudo().browse(int(employee_id))
        if Employee.user_id and Employee.user_id.partner_id:
            if not Employee.user_id.partner_id.calendar_verify_availability(date_start, date_end):
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
        partner_ids = list(set([Employee.user_id.partner_id.id] + [partner.id]))
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
            'user_id': Employee.user_id.id,
            'meeting_url': f"https://{booking_type.meeting_base_url}/{str(uuid.uuid1())}"
        }
        event = self._create_event(request, Employee, data)
        event.attendee_ids.filtered(lambda attendee: attendee.partner_id.id == partner.id).write({'public_user': True})
        event.attendee_ids.write({'state': 'accepted'})
        return request.redirect('/website/calendar/view/' + event.access_token + '?message=new'+'&title='+title)
        

    def _create_event(self, request, Employee, data):
        return request.env['calendar.event'].sudo().with_context(allowed_company_ids=Employee.user_id.company_ids.ids).create(data)

    @http.route(['/website/calendar/view/<string:access_token>'], type='http', auth="public", website=True)
    def calendar_booking_view(self, access_token, edit=False, message=False, description=False, title=False, **kwargs):
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event:
            return request.not_found()

        timezone = request.session.get('timezone')
        if not timezone:
            timezone = request.env.context.get('tz') or event.booking_type_id.booking_tz or event.partner_ids and event.partner_ids[0].tz or event.user_id.tz or 'UTC'
            request.session['timezone'] = timezone
        tz_session = pytz.timezone(timezone)

        date_start_suffix = ""
        format_func = format_datetime
        if not event.allday:
            url_date_start = fields.Datetime.from_string(event.start).strftime('%Y%m%dT%H%M%SZ')
            url_date_stop = fields.Datetime.from_string(event.stop).strftime('%Y%m%dT%H%M%SZ')
            date_start = fields.Datetime.from_string(event.start).replace(tzinfo=pytz.utc).astimezone(tz_session)
        else:
            url_date_start = url_date_stop = fields.Date.from_string(event.start_date).strftime('%Y%m%d')
            date_start = fields.Date.from_string(event.start_date)
            format_func = format_date
            date_start_suffix = _(', All Day')

        locale = get_lang(request.env).code
        day_name = format_func(date_start, 'EEE', locale=locale)
        date_start = day_name + ' ' + format_func(date_start, locale=locale) + date_start_suffix
        details = event.booking_type_id and event.booking_type_id.message_confirmation or event.description or ''
        params = {
            'action': 'TEMPLATE',
            'text': event.name,
            'dates': url_date_start + '/' + url_date_stop,
            'details': html2plaintext(details.encode('utf-8'))
        }
        if event.location:
            params.update(location=event.location.replace('\n', ' '))
        encoded_params = url_encode(params)
        google_url = 'https://www.google.com/calendar/render?' + encoded_params

        return request.render("website_calendar_ce.booking_validated", {
            'event': event,
            'datetime_start': date_start,
            'google_url': google_url,
            'message': message,
            'edit': edit,
            'description': description if description else _("Fill your personal information in the form below, and confirm the booking. We'll send an invite to your email address"),
            'title': title if title else _("Book meeting"),
        })

    @http.route(['/website/calendar/ics/<string:access_token>.ics'], type='http', auth="public", website=True)
    def calendar_booking_ics(self, access_token, **kwargs):
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event or not event.attendee_ids:
            return request.not_found()
        files = event._get_ics_file()
        content = files[event.id]
        return request.make_response(content, [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Length', len(content)),
            ('Content-Disposition', 'attachment; filename=Booking.ics')
        ])

    @http.route(['/website/calendar/cancel/<string:access_token>'], type='http', auth="public", website=True)
    def calendar_booking_cancel(self, access_token, **kwargs):
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event:
            return request.not_found()
        if fields.Datetime.from_string(event.allday and event.start or event.start) < datetime.now() + relativedelta(hours=event.booking_type_id.min_cancellation_hours):
            return request.redirect('/website/calendar/view/' + access_token + '?message=no-cancel')
        event.unlink()
        return request.redirect('/website/calendar?message=cancel')

    # Snippets
    @http.route(['/website/calendar_snippet/<model("calendar.booking.type"):booking_type>/booking'], type='http', auth="public",
                website=True)
    def calendar_booking_snippet(self, booking_type=None, employee_id=None, timezone=None, failed=False, description=None, title=None, **kwargs):
        request.session['timezone'] = timezone or booking_type.booking_tz
        Employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None
        Slots = booking_type.sudo()._get_booking_slots(request.session['timezone'], Employee)
        return request.render("website_calendar_ce.booking_snippet", {
            'booking_type': booking_type,
            'timezone': request.session['timezone'],
            'failed': failed,
            'slots': Slots,
            'description': description if description else _("Fill your personal information in the form below, and confirm the booking. We'll send an invite to your email address"),
            'title': title if title else _("Book meeting"),
        })

