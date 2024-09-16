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

import json
import calendar as cal
import random
import pytz
from datetime import datetime, timedelta, time
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from babel.dates import format_datetime

from odoo import api, fields, models, _
from odoo.tools.misc import get_lang
from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.http_routing.models.ir_http import slug
from odoo.exceptions import ValidationError
import pandas as pd


class CalendarBookingType(models.Model):
    _name = "calendar.booking.type"
    _description = "Online Booking Type"
    _inherit = ['mail.thread', "website.seo.metadata", 'website.published.mixin']
    _order = "sequence"
    
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index = True)
    
    sequence = fields.Integer('Sequence')
    name = fields.Char('Booking Type', required=True, translate=True)
    min_schedule_hours = fields.Float('Schedule before (hours)', required=True, default=1.0)
    max_schedule_days = fields.Integer('Schedule not after (days)', required=True, default=15)
    min_cancellation_hours = fields.Float('Cancel Before (hours)', required=True, default=1.0)
    booking_duration = fields.Float('Booking Duration', required=True, default=1.0)

    reminder_ids = fields.Many2many('calendar.alarm', string="Reminders")
    location = fields.Char('Location', help="Location of the booking")
    message_confirmation = fields.Html('Confirmation Message', translate=True)
    message_intro = fields.Html('Introduction Message', translate=True)

    country_ids = fields.Many2many(
        'res.country', 'website_calendar_type_country_rel', string='Restrict Countries',
        help="If empty, allow visitors from any country, otherwise only allow visitors from selected countries")
    question_ids = fields.One2many('calendar.booking.question', 'booking_type_id', string='Questions', copy=True)

    slot_ids = fields.One2many('calendar.booking.slot', 'booking_type_id', 'Availabilities', copy=True)
    booking_tz = fields.Selection(
        _tz_get, string='Timezone', required=True, default=lambda self: self.env.user.tz,
        help="Timezone where booking take place")

    employee_ids = fields.Many2many(
        'hr.employee', 
        'website_calendar_type_employee_rel',
        domain=[('user_id', '!=', False)], 
        string='Employees', 
        default=lambda self: self._get_default_employee_ids()
    )

    @api.model
    def _get_default_employee_ids(self):
        # Search for an employee linked to the current user
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        
        # If no employee exists, create one
        if not employee:
            employee = self.env['hr.employee'].create({
                'name': self.env.user.name,
                'user_id': self.env.user.id,
                'company_id': self.env.user.company_id.id
            })
        
        return employee.ids

    assignation_method = fields.Selection([
        ('random', 'Random'),
        ('chosen', 'Chosen by the Customer')], string='Assignation Method', default='random',
        help="How employees will be assigned to meetings customers book on your website.")
    booking_count = fields.Integer('# Bookings', compute='_compute_booking_count')
    meeting_base_url = fields.Char('Meeting base url')
    @api.model
    def find_all_bookings(self):
        bookings = []
        for booking in self.env[self._name].sudo().search([('website_published', '=', True)]):
            booking_line = {}
            booking_line['id'] = booking.id
            booking_line['name'] = booking.name
            bookings.append(booking_line)
        return json.dumps(bookings)

    @api.model
    def get_booking_details(self, booking_id=False):
        if booking_id:
            _booking_id = self.env[self._name].sudo().browse(booking_id)
            booking_details = {
                'booking_id': _booking_id.id,
                'timezone': _booking_id.booking_tz,
                'assignation_method': _booking_id.assignation_method,
                'suggested_employees': [{
                    'employee_id': emp.id,
                    'employee_name': emp.name,
                } for emp in _booking_id.employee_ids]
            }
            return booking_details
        return False

    def _compute_booking_count(self):
        meeting_data = self.env['calendar.event'].read_group([('booking_type_id', 'in', self.ids)], ['booking_type_id'],
                                                             ['booking_type_id'])
        mapped_data = {m['booking_type_id'][0]: m['booking_type_id_count'] for m in meeting_data}
        for booking_type in self:
            booking_type.booking_count = mapped_data.get(booking_type.id, 0)

    def _compute_website_url(self):
        for booking_type in self:
            booking_type.website_url = '/website/calendar/%s/booking' % (slug(booking_type),)

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        default['name'] = self.name + _(' (copy)')
        return super(CalendarBookingType, self).copy(default=default)

    def action_calendar_meetings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("calendar.action_calendar_event")
        action['context'] = {
            'default_booking_type_id': self.id,
            'search_default_booking_type_id': self.id
        }
        
        return action

    # --------------------------------------
    # Slots Generation
    # --------------------------------------

    def _slots_generate(self, first_day, last_day, timezone):
        """ Generate all booking slots (in naive UTC, booking timezone, and given (visitors) timezone)
            between first_day and last_day (datetimes in booking timezone)

            :return: [ {'slot': slot_record, <timezone>: (date_start, date_end), ...},
                      ... ]
        """

        def append_slot(day, slot):
            local_start = appt_tz.localize(
                datetime.combine(day, time(hour=int(slot.hour), minute=int(round((slot.hour % 1) * 60)))))
            local_end = appt_tz.localize(
                datetime.combine(day,
                                 time(hour=int(slot.hour), minute=int(round((slot.hour % 1) * 60)))) + relativedelta(
                    hours=self.booking_duration))
            slots.append({
                self.booking_tz: (
                    local_start,
                    local_end,
                ),
                timezone: (
                    local_start.astimezone(requested_tz),
                    local_end.astimezone(requested_tz),
                ),
                'UTC': (
                    local_start.astimezone(pytz.UTC).replace(tzinfo=None),
                    local_end.astimezone(pytz.UTC).replace(tzinfo=None),
                ),
                'slot': slot,
            })

        appt_tz = pytz.timezone(self.booking_tz)
        requested_tz = pytz.timezone(timezone)

        slots = []
        for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == first_day.isoweekday()):
            if slot.hour > first_day.hour + first_day.minute / 60.0:
                append_slot(first_day.date(), slot)
        slot_weekday = [int(weekday) - 1 for weekday in self.slot_ids.mapped('weekday')]
        for day in rrule.rrule(rrule.DAILY,
                               dtstart=first_day.date() + timedelta(days=1),
                               until=last_day.date(),
                               byweekday=slot_weekday):
            for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == day.isoweekday()):
                append_slot(day, slot)
        return slots

    def _slots_available(self, slots, first_day, last_day, employee=None):
        """ Fills the slot stucture with an available employee

            :param slots: slots structure generated by _slots_generate
            :param first_day: start datetime in UTC
            :param last_day: end datetime in UTC
            :param employee: if set, only consider this employee
                             if not set, consider all employees assigned to this booking type
        """

        def is_work_available(start_dt, end_dt, intervals):
            """ check if the slot is contained in the employee's work hours (defined by intervals)
            """

            def find_start_index():
                """ find the highest index of intervals for which the start_date (element [0]) is before (or at) start_dt
                """

                def recursive_find_index(lower_bound, upper_bound):
                    if upper_bound - lower_bound <= 1:
                        if intervals[upper_bound][0] <= start_dt:
                            return upper_bound
                        return lower_bound
                    index = (upper_bound + lower_bound) // 2
                    if intervals[index][0] <= start_dt:
                        return recursive_find_index(index, upper_bound)
                    else:
                        return recursive_find_index(lower_bound, index)

                if start_dt <= intervals[0][0] - tolerance:
                    return -1
                if end_dt >= intervals[-1][1] + tolerance:
                    return -1
                return recursive_find_index(0, len(intervals) - 1)

            if not intervals:
                return False

            tolerance = timedelta(minutes=1)
            start_index = find_start_index()
            if start_index != -1:
                for index in range(start_index, len(intervals)):
                    if intervals[index][1] >= end_dt - tolerance:
                        return True
                    if len(intervals) == index + 1 or intervals[index + 1][0] - intervals[index][1] > tolerance:
                        return False
            return False

        def is_calendar_available(slot, events, employee):
            """ Returns True if the given slot doesn't collide with given events for the employee
            """
            start_dt = slot['UTC'][0]
            end_dt = slot['UTC'][1]

            event_in_scope = lambda ev: (
                    fields.Date.to_date(ev.start) <= fields.Date.to_date(end_dt)
                    and fields.Date.to_date(ev.stop) >= fields.Date.to_date(start_dt)
            )

            for ev in events.filtered(event_in_scope):
                if ev.allday:
                    # allday events are considered to take the whole day in the related employee's timezone
                    event_tz = pytz.timezone(ev.event_tz or employee.user_id.tz or self.env.user.tz or slot[
                        'slot'].booking_type_id.booking_tz or 'UTC')
                    ev_start_dt = datetime.combine(fields.Date.from_string(ev.start_date), time.min)
                    ev_stop_dt = datetime.combine(fields.Date.from_string(ev.stop_date), time.max)
                    ev_start_dt = event_tz.localize(ev_start_dt).astimezone(pytz.UTC).replace(tzinfo=None)
                    ev_stop_dt = event_tz.localize(ev_stop_dt).astimezone(pytz.UTC).replace(tzinfo=None)
                    if ev_start_dt < end_dt and ev_stop_dt > start_dt:
                        return False
                elif fields.Datetime.to_datetime(ev.start) < end_dt and fields.Datetime.to_datetime(ev.stop) > start_dt:
                    return False
            return True

        workhours = {}
        meetings = {}

        # With context will be used in resource.calendar to force the referential user
        # for work interval computing to the *user linked to the employee*
        available_employees = [emp.with_context(tz=emp.user_id.tz) for emp in (employee or self.employee_ids)]
        random.shuffle(available_employees)
        for slot in slots:
            for emp_pos, emp in enumerate(available_employees):
                if emp_pos not in workhours:
                    workhours[emp_pos] = [
                        (interval[0].astimezone(pytz.UTC).replace(tzinfo=None),
                         interval[1].astimezone(pytz.UTC).replace(tzinfo=None))
                        for interval in emp.resource_calendar_id._work_intervals_batch(
                            first_day, last_day, resources=emp.resource_id,
                        )[emp.resource_id.id]
                    ]

                if is_work_available(slot['UTC'][0], slot['UTC'][1], workhours[emp_pos]):
                    if emp_pos not in meetings:
                        # note: no check is made on the attendee's status (accepted/declined/...)
                        meetings[emp_pos] = self.env['calendar.event'].search([
                            ('partner_ids.user_ids', '=', emp.user_id.id),
                            ('start', '<', fields.Datetime.to_string(last_day.replace(hour=23, minute=59, second=59))),
                            ('stop', '>', fields.Datetime.to_string(first_day.replace(hour=0, minute=0, second=0)))
                        ])

                    if is_calendar_available(slot, meetings[emp_pos], emp):
                        slot['employee_id'] = emp
                        break

    def _get_booking_slots(self, timezone, employee=None):
        """ Fetch available slots to book an booking
            :param timezone: timezone string e.g.: 'Europe/Brussels' or 'Etc/GMT+1'
            :param employee: if set will only check available slots for this employee
            :returns: list of dicts (1 per month) containing available slots per day per week.
                      complex structure used to simplify rendering of template

            TODO: this needs to be improved if it will be used
        """
        self.ensure_one()
        appt_tz = pytz.timezone(self.booking_tz)
        requested_tz = pytz.timezone(timezone)
        first_day = requested_tz.fromutc(datetime.utcnow() + relativedelta(hours=self.min_schedule_hours))
        last_day = requested_tz.fromutc(datetime.utcnow() + relativedelta(days=self.max_schedule_days))
        
        today = requested_tz.fromutc(datetime.utcnow())
        start = today
        

        difference = relativedelta(last_day, first_day)
        months_diff = difference.years * 12 + difference.months
        if abs(months_diff ) < 1:
            last_day += relativedelta(months=1)

        # Compute available slots (ordered)
        slots = self._slots_generate(first_day.astimezone(appt_tz), last_day.astimezone(appt_tz), timezone)
        if not employee or employee in self.employee_ids:
            self._slots_available(slots, first_day.astimezone(pytz.UTC), last_day.astimezone(pytz.UTC), employee)

        # Compute calendar rendering and inject available slots       
        month_dates_calendar = cal.Calendar(0).monthdatescalendar
        months = []
        while (start.year, start.month) <= (last_day.year, last_day.month):
            dates = month_dates_calendar(start.year, start.month)
            for week_index, week in enumerate(dates):
                for day_index, day in enumerate(week):
                    mute_cls = weekend_cls = today_cls = None
                    today_slots = []
                    if day.weekday() in (cal.SUNDAY, cal.SATURDAY):
                        weekend_cls = 'o_weekend'
                    if day == today.date() and day.month == today.month:
                        today_cls = 'o_today'
                    if day.month != start.month:
                        mute_cls = 'text-muted o_mute_day'
                    else:
                        # slots are ordered, so check all unprocessed slots from until > day
                        while slots and (slots[0][timezone][0].date() <= day):
                            if (slots[0][timezone][0].date() == day) and ('employee_id' in slots[0]):
                                today_slots.append({
                                    'employee_id': slots[0]['employee_id'].id,
                                    'datetime': slots[0][timezone][0].strftime('%Y-%m-%d %H:%M:%S'),
                                    'hours': slots[0][timezone][0].strftime('%H:%M')
                                })
                            slots.pop(0)
                    dates[week_index][day_index] = {
                        'day': day,
                        'slots': today_slots,
                        'mute_cls': mute_cls,
                        'weekend_cls': weekend_cls,
                        'today_cls': today_cls
                    }

            months.append({
                'month': format_datetime(start, 'MMMM Y', locale=get_lang(self.env).code),
                'weeks': dates
            })
            start = start + relativedelta(months=1)
        return months

    def _get_paginated_booking_slots(self, timezone, employee=None, month=0):
        booking_slots = self._get_booking_slots(timezone, employee)
        print(booking_slots)
        try:
            return [booking_slots[month], booking_slots[month + 1]]
        except IndexError as e:
            return []

    def open_booking_wizard(self):
        return {
            'view_mode': 'form',
            'res_model': 'calendar.booking.slot.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_id': self.env.ref('website_calendar_ce.time_slot_wizard').id,
            'context': {
                'default_booking_id': self.id,
                'default_booking_duration': self.booking_duration
            }
        }


class CalendarBookingSlot(models.Model):
    _name = "calendar.booking.slot"
    _description = "Online Booking : Time Slot"
    _rec_name = "weekday"
    _order = "weekday, hour"

    booking_type_id = fields.Many2one('calendar.booking.type', 'Booking Type', ondelete='cascade')
    weekday = fields.Selection([
        ('1', 'Monday'),
        ('2', 'Tuesday'),
        ('3', 'Wednesday'),
        ('4', 'Thursday'),
        ('5', 'Friday'),
        ('6', 'Saturday'),
        ('7', 'Sunday'),
    ], string='Week Day', required=True)
    hour = fields.Float('Starting Hour', required=True, default=8.0)

    @api.constrains('hour')
    def check_hour(self):
        if any(self.filtered(lambda slot: 0.00 > slot.hour or slot.hour >= 24.00)):
            raise ValidationError(_("Please enter a valid hour between 0:00 to 24:00 for your slots."))

    def name_get(self):
        weekdays = dict(self._fields['weekday'].selection)
        return self.mapped(lambda slot: (
            slot.id, "%s, %02d:%02d" % (weekdays.get(slot.weekday), int(slot.hour), int(round((slot.hour % 1) * 60)))))


class CalendarBookingSlotWizard(models.TransientModel):
    _name = "calendar.booking.slot.wizard"
    _description = "Set Time Slot"

    time_from = fields.Char(string="Starting Hour", required=True, default="08:00")
    time_to = fields.Char(string="Ending Hour", required=True, default="17:00")
    booking_duration = fields.Char(string="Booking Duration", required=True)
    booking_id = fields.Many2one('calendar.booking.type', string="Booking", required=True)

    monday = fields.Boolean(string="Monday", default=True)
    tuesday = fields.Boolean(string="Tuesday", default=True)
    wednesday = fields.Boolean(string="Wednesday", default=True)
    thursday = fields.Boolean(string="Thursday", default=True)
    friday = fields.Boolean(string="Friday", default=True)
    saturday = fields.Boolean(string="Saturday")
    sunday = fields.Boolean(string="Sunday")

    def compute_slot(self):
        fmt = '%H:%M'
        time_from = datetime.strptime(self.time_from, fmt)
        time_to = datetime.strptime(self.time_to, fmt)
        frequency = '%sH' % self.booking_duration
        date_range = pd.date_range(start=time_from, end=time_to, freq=frequency)
        if self.monday:
            self._populate_slot(date_range, fmt, 1)
        if self.tuesday:
            self._populate_slot(date_range, fmt, 2)
        if self.wednesday:
            self._populate_slot(date_range, fmt, 3)
        if self.thursday:
            self._populate_slot(date_range, fmt, 4)
        if self.friday:
            self._populate_slot(date_range, fmt, 5)
        if self.saturday:
            self._populate_slot(date_range, fmt, 6)
        if self.sunday:
            self._populate_slot(date_range, fmt, 7)

    def conv_time_float(self, time):
        vals = time.split(':')
        t, hours = divmod(float(vals[0]), 24)
        t, minutes = divmod(float(vals[1]), 60)
        minutes = minutes / 60.0
        return hours + minutes

    def _populate_slot(self, date_range, fmt, weekday):
        for time_interval in date_range:
            float_hour_string = time_interval.strftime(fmt)
            float_hour = self.conv_time_float(float_hour_string)
            self.env['calendar.booking.slot'].create({
                'booking_type_id': self.booking_id.id,
                'hour': float_hour,
                'weekday': str(weekday)
            })


class CalendarBookingQuestion(models.Model):
    _name = "calendar.booking.question"
    _description = "Online Booking : Questions"
    _order = "sequence"

    sequence = fields.Integer('Sequence')
    booking_type_id = fields.Many2one('calendar.booking.type', 'Booking Type', ondelete="cascade")
    name = fields.Char('Question', translate=True, required=True)
    placeholder = fields.Char('Placeholder', translate=True)
    question_required = fields.Boolean('Required Answer')
    question_type = fields.Selection([
        ('char', 'Single line text'),
        ('text', 'Multi-line text'),
        ('select', 'Dropdown (one answer)'),
        ('radio', 'Radio (one answer)'),
        ('checkbox', 'Checkboxes (multiple answers)')], 'Question Type', default='char')
    answer_ids = fields.Many2many('calendar.booking.answer', 'calendar_booking_question_answer_rel', 'question_id',
                                  'answer_id', string='Available Answers')


class CalendarBookingAnswer(models.Model):
    _name = "calendar.booking.answer"
    _description = "Online Booking : Answers"

    question_id = fields.Many2many('calendar.booking.question', 'calendar_booking_question_answer_rel', 'answer_id',
                                   'question_id', string='Questions')
    name = fields.Char('Answer', translate=True, required=True)


class CalendatEvent(models.Model):
    _inherit = 'calendar.event'

    state = fields.Selection([('draft', 'Unconfirmed'), ('open', 'Confirmed')], string='Status', readonly=True,
                             tracking=True, default='draft')
