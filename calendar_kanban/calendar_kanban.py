# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution, third party addon
#    Copyright (C) 2004-2016 Vertel AB (<http://vertel.se>).
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
from openerp import models, fields, api, _
import time
import datetime
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)

class calendar_event(models.Model):
    _inherit = 'calendar.event'

    # return a list of next six weeks from now include this week
    def next_six_weeks():
        now = datetime.date.today()
        return[
            str(now.isocalendar()[0]) + '-W' + str(now.isocalendar()[1]),
            str((now + datetime.timedelta(weeks=1)).isocalendar()[0]) + '-W' + str((now + datetime.timedelta(weeks=1)).isocalendar()[1]),
            str((now + datetime.timedelta(weeks=2)).isocalendar()[0]) + '-W' + str((now + datetime.timedelta(weeks=2)).isocalendar()[1]),
            str((now + datetime.timedelta(weeks=3)).isocalendar()[0]) + '-W' + str((now + datetime.timedelta(weeks=3)).isocalendar()[1]),
            str((now + datetime.timedelta(weeks=4)).isocalendar()[0]) + '-W' + str((now + datetime.timedelta(weeks=4)).isocalendar()[1]),
            str((now + datetime.timedelta(weeks=5)).isocalendar()[0]) + '-W' + str((now + datetime.timedelta(weeks=5)).isocalendar()[1]),
        ]

    # select attribut to week_number field
    WEEKS = [
        ('Undefined', ''),
        (next_six_weeks()[0], ''),
        (next_six_weeks()[1], ''),
        (next_six_weeks()[2], ''),
        (next_six_weeks()[3], ''),
        (next_six_weeks()[4], ''),
        (next_six_weeks()[5], ''),
    ]

    # which week shows folded by default
    FOLDED_WEEK = [
        next_six_weeks()[3],
        next_six_weeks()[4],
        next_six_weeks()[5],
    ]

    color = fields.Integer(string='Color Index')
    week_number = fields.Char(string='Week number', compute='get_week_number', inverse='set_week_number', readonly=True, store=True, default='Undefined')
    weekday = fields.Char(string='Weekday', readonly=True, default='Undefined')

    def get_iso_week_day(self, iso_weekday_number):
        return iso_weekday_number + 1 if iso_weekday_number < 6 else 0

    def get_week_day(self, weekday_number):
        if weekday_number == 1:
            return 'Monday'
        elif weekday_number == 2:
            return 'Tuesday'
        elif weekday_number == 3:
            return 'Wednesday'
        elif weekday_number == 4:
            return 'Thursday'
        elif weekday_number == 5:
            return 'Friday'
        elif weekday_number == 6:
            return 'Saturday'
        elif weekday_number == 0:
            return 'Sunday'
    
    @api.model
    def _change_week_and_weekday(self, start):
        week_day = self.get_iso_week_day(fields.Date.from_string(start).weekday())
        week_number = str(fields.Date.from_string(start).isocalendar()[0]) + '-W' + str(fields.Date.from_string(start).isocalendar()[1])
        weekday = self.get_week_day(week_day)
        return (week_number, weekday)
    
    @api.v7
    def onchange_dates(self, cr, uid, ids, fromtype, start=False, end=False, checkallday=False, allday=False, context=None):
        res = super(calendar_event, self).onchange_dates(cr, uid, ids, fromtype, start, end, checkallday, allday, context)
        if not res:
            res = {}
        if not res.get('value'):
            res['value'] = {}
        start = res['value'].get('start') or start
        if start:
            res['value']['week_number'], res['value']['weekday'] = self._change_week_and_weekday(cr, uid, start, context)
        return res
        
    @api.v7
    def onchange_allday(self, cr, uid, ids, start=False, end=False, starttime=False, endtime=False, startdatetime=False, enddatetime=False, checkallday=False, context=None):
        res = super(calendar_event, self).onchange_allday(cr, uid, ids, start, end, starttime, endtime, startdatetime, enddatetime, checkallday, context)
        if not res:
            res = {}
        if not res.get('value'):
            res['value'] = {}
        start = res['value'].get('start') or start
        if start:
            res['value']['week_number'], res['value']['weekday'] = self._change_week_and_weekday(cr, uid, start, context)
        return res
    
    @api.one
    def get_week_number(self):
        if self.start:
            self.week_number, self.weekday = self._change_week_and_weekday(self.start)

    @api.one
    def set_week_number(self):
        if self.week_number == 'Undefined':
            self.write({
                'start_datetime': '2010-01-01 00:00:00',
                'stop_datetime': '2010-01-01 00:00:00',
            })
        else:
            if self.allday:
                week_day = self.get_iso_week_day(fields.Date.from_string(self.start_date).weekday())
                self.write({
                    'start_date': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + str(week_day), '%Y-W%W-%w')),
                    'stop_date': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + str(week_day), '%Y-W%W-%w')),
                })
            if not self.allday:
                week_day = self.get_iso_week_day(fields.Date.from_string(self.start_datetime).weekday())
                meeting_start = str(fields.Datetime.from_string(self.start_datetime).hour) + ':' + str(fields.Datetime.from_string(self.start_datetime).minute) + ':' + str(fields.Datetime.from_string(self.start_datetime).second)
                meeting_stop = str(fields.Datetime.from_string(self.stop_datetime).hour) + ':' + str(fields.Datetime.from_string(self.stop_datetime).minute) + ':' + str(fields.Datetime.from_string(self.stop_datetime).second)
                self.write({
                    'start_datetime': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + str(week_day), '%Y-W%W-%w')) + ' ' + meeting_start,
                    'stop_datetime': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + str(week_day), '%Y-W%W-%w')) + ' ' + meeting_stop,
                })

    @api.model
    def weeks_list(self, present_ids, domain, **kwargs):
        folded = {key: (key in self.FOLDED_WEEK) for key, _ in self.WEEKS}
        return self.WEEKS[:], folded

    # group list for kanban view
    _group_by_full = {
        'week_number': weeks_list,
    }

    def _read_group_fill_results(self, cr, uid, domain, groupby,
                                 remaining_groupbys, aggregated_fields,
                                 count_field, read_group_result,
                                 read_group_order=None, context=None):
        """
        The method seems to support grouping using m2o fields only,
        while we want to group by a week_number field.
        Hence the code below - it replaces simple week_number values
        with (value, name) tuples.
        """
        if groupby == 'week_number':
            WEEK_DICT = dict(self.WEEKS)
            for result in read_group_result:
                week = result['week_number']
                result['week_number'] = (week, WEEK_DICT.get(week))
        return super(calendar_event, self)._read_group_fill_results(
            cr, uid, domain, groupby, remaining_groupbys, aggregated_fields,
            count_field, read_group_result, read_group_order, context
        )
    
