# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Enterprise Management Solution, third party addon
#    Copyright (C) 2004-2018 Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from odoo import models, fields, api, _
import time
import datetime
from datetime import date, datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import logging
_logger = logging.getLogger(__name__)


class CalendarYear(models.Model):
    _name = 'calendar.year'

    name = fields.Integer(string='Name')
    week_ids = fields.One2many(string='Week', comodel_name='calendar.week', inverse_name='year_id')

    @api.multi
    def create_weeks(self):
        begin = datetime.strptime('%s-01-01' %self.name, '%Y-%m-%d').date()
        end = datetime.strptime('%s-12-31' %self.name, '%Y-%m-%d').date()
        days = [begin]
        date = begin
        while (date < end):
            date += timedelta(days=1)
            days.append(date)
        weeks = []
        for day in days:
            if day.isocalendar()[0] == self.name:
                week = '%s-W%s' %(day.isocalendar()[0], day.isocalendar()[1])
                if week not in weeks:
                    weeks.append(week)
                    date_start = fields.Date.to_string(self.env['calendar.week'].find_week_begin(day))
                    date_end = fields.Date.to_string(self.env['calendar.week'].find_week_end(day))
                    w = self.env['calendar.week'].search(['|', ('name', '=', week), '|', ('date_start', '=', date_start), ('date_end', '=', date_end)])
                    if w:
                        w.write({
                            'name': week,
                            'year_id': self.id,
                            'week_number': day.isocalendar()[1],
                            'date_start': date_start,
                            'date_end': date_end,
                        })
                    else:
                        self.env['calendar.week'].create({
                            'name': week,
                            'year_id': self.id,
                            'week_number': day.isocalendar()[1],
                            'date_start': date_start,
                            'date_end': date_end,
                        })


class CalendarWeek(models.Model):
    _name = 'calendar.week'

    name = fields.Char(string='Name')
    year_id = fields.Many2one(string='Year', comodel_name='calendar.year')
    week_number = fields.Integer(string='Week Number')
    date_start = fields.Date(string='Date Start')
    date_end = fields.Date(string='Date End')

    @api.model
    def find_week_begin(self, date):
        return date + timedelta(days=-date.weekday(), weeks=0)

    @api.model
    def find_week_end(self, date):
        return date + timedelta(days=-date.weekday()-1, weeks=1)


class Meeting(models.Model):
    _inherit = 'calendar.event'

    @api.model
    def _read_group_week_ids(self, weeks, domain, order):
        current_week_monday = self.env['calendar.week'].find_week_begin(fields.Date.from_string(fields.Date.today()))
        week_ids = self.env['calendar.week'].browse()
        for idx in range(0, 6):
            week_ids |= self.env['calendar.week'].search([('date_start', '=', fields.Date.to_string(current_week_monday + timedelta(days=7*idx)))])
        return week_ids
        #~ if self.week_id:
            #~ week_ids = self.env['calendar.week'].browse()
            #~ for idx in range(0, 6):
                #~ monday = fields.Date.from_string(self.week_id.date_start) + timedelta(weeks=idx)
                #~ week_ids |= self.env['calendar.week'].search([('date_start', '=', fields.Date.to_string(monday))])
            #~ return week_ids

    color = fields.Integer(string='Color Index')
    week_id = fields.Many2one(string='Week', comodel_name='calendar.week', group_expand='_read_group_week_ids', store=True)
    weekday = fields.Selection(string='Weekday', selection=[('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'), ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'), ('sunday', 'Sunday'),], default='monday', store=True)
    weekday_changed = fields.Boolean(compute='compute_weekday_changed')

    @api.onchange('start_date', 'start_datetime')
    def onchange_start_date_datetime(self):
        if self.weekday_changed:
            self.weekday_changed = False
            return
        self.weekday_changed = True
        date = None
        if self.start_date or self.start_datetime:
            if self.allday:
                date = fields.Date.from_string(self.start_date)
            else:
                date = fields.Date.from_string(self.start_datetime)
            if date:
                self.weekday = self.get_week_day(date.weekday())
                mondy = self.env['calendar.week'].find_week_begin(date)
                week = self.env['calendar.week'].search([('date_start', '=', fields.Date.to_string(mondy))])
                if not week:
                    raise Warning(_('Please generate weeks'))
                else:
                    self.week_id = week

    @api.onchange('week_id', 'weekday')
    def onchange_week_id_weekday(self):
        if self.weekday_changed:
            self.weekday_changed = False
            return
        self.weekday_changed = True
        date = fields.Date.to_string(fields.Date.from_string(self.week_id.date_start) + timedelta(days=self.get_week_day_int(self.weekday)))
        if self.allday:
            self.start_date = date
        else:
            self.start_datetime = '%s 00:00:00' %date

    @api.one
    def compute_weekday_changed(self):
        self.weekday_changed = False

    def get_week_day(self, weekday_number):
        if weekday_number == 0:
            return 'monday'
        elif weekday_number == 1:
            return 'tuesday'
        elif weekday_number == 2:
            return 'wednesday'
        elif weekday_number == 3:
            return 'thursday'
        elif weekday_number == 4:
            return 'friday'
        elif weekday_number == 5:
            return 'saturday'
        elif weekday_number == 6:
            return 'sunday'

    def get_week_day_int(self, weekday):
        if weekday == 'monday':
            return 0
        elif weekday == 'tuesday':
            return 1
        elif weekday == 'wednesday':
            return 2
        elif weekday == 'thursday':
            return 3
        elif weekday == 'friday':
            return 4
        elif weekday == 'saturday':
            return 5
        elif weekday == 'sunday':
            return 6
