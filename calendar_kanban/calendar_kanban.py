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
from datetime import date, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import logging
_logger = logging.getLogger(__name__)


class Meeting(models.Model):
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
    week_number = fields.Char(string='Week number', compute='get_week_number', inverse='set_week_number', store=True, default='Undefined', group_expand=lambda self: self.WEEKS)
    weekday = fields.Selection(string='Weekday', selection=[('undefined', 'Undefined'), ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'), ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'), ('sunnday', 'Sunday'),], default='undefined')

    def get_iso_week_day(self, iso_weekday_number):
        return iso_weekday_number + 1 if iso_weekday_number < 6 else 0

    def get_week_day(self, weekday_number):
        if weekday_number == 1:
            return 'monday'
        elif weekday_number == 2:
            return 'tuesday'
        elif weekday_number == 3:
            return 'wednesday'
        elif weekday_number == 4:
            return 'thursday'
        elif weekday_number == 5:
            return 'friday'
        elif weekday_number == 6:
            return 'saturday'
        elif weekday_number == 0:
            return 'sunday'

    @api.model
    def _change_week_and_weekday(self, start):
        week_day = self.get_iso_week_day(fields.Date.from_string(start).weekday())
        week_number = str(fields.Date.from_string(start).isocalendar()[0]) + '-W' + str(fields.Date.from_string(start).isocalendar()[1])
        weekday = self.get_week_day(week_day)
        return (week_number, weekday)

    @api.multi
    def onchange_dates(self, fromtype, start=False, end=False, checkallday=False, allday=False):
        value = {}
        if checkallday != allday:
            return value
        value['allday'] = checkallday  # Force to be rewrited
        if allday:
            if fromtype == 'start' and start:
                start = datetime.strptime(start, DEFAULT_SERVER_DATE_FORMAT)
                value['start_datetime'] = datetime.strftime(start, DEFAULT_SERVER_DATETIME_FORMAT)
                value['start'] = datetime.strftime(start, DEFAULT_SERVER_DATETIME_FORMAT)

            if fromtype == 'stop' and end:
                end = datetime.strptime(end, DEFAULT_SERVER_DATE_FORMAT)
                value['stop_datetime'] = datetime.strftime(end, DEFAULT_SERVER_DATETIME_FORMAT)
                value['stop'] = datetime.strftime(end, DEFAULT_SERVER_DATETIME_FORMAT)
        else:
            if fromtype == 'start' and start:
                start = datetime.strptime(start, DEFAULT_SERVER_DATETIME_FORMAT)
                value['start_date'] = datetime.strftime(start, DEFAULT_SERVER_DATE_FORMAT)
                value['start'] = datetime.strftime(start, DEFAULT_SERVER_DATETIME_FORMAT)
            if fromtype == 'stop' and end:
                end = datetime.strptime(end, DEFAULT_SERVER_DATETIME_FORMAT)
                value['stop_date'] = datetime.strftime(end, DEFAULT_SERVER_DATE_FORMAT)
                value['stop'] = datetime.strftime(end, DEFAULT_SERVER_DATETIME_FORMAT)
        if not value.get('value'):
            value['value'] = {}
        start = value['value'].get('start') or start
        if start:
            value['value']['week_number'], value['value']['weekday'] = self._change_week_and_weekday(start)
        return {'value': value}

    @api.multi
    def onchange_allday(self, start=False, end=False, starttime=False, endtime=False, startdatetime=False, enddatetime=False, checkallday=False):
        value = {}
        if not ((starttime and endtime) or (start and end)):  # At first intialize, we have not datetime
            return value
        if checkallday:  # from datetime to date
            startdatetime = startdatetime or start
            if startdatetime:
                start = datetime.strptime(startdatetime, DEFAULT_SERVER_DATETIME_FORMAT)
                value['start_date'] = fields.Date.context_today(timestamp=start)

            enddatetime = enddatetime or end
            if enddatetime:
                end = datetime.strptime(enddatetime, DEFAULT_SERVER_DATETIME_FORMAT)
                value['stop_date'] = fields.date.context_today(timestamp=end)
        else:  # from date to datetime
            user = self.env.user
            tz = pytz.timezone(user.tz) if user.tz else pytz.utc

            if starttime:
                start = openerp.fields.Datetime.from_string(starttime)
                startdate = tz.localize(start)  # Add "+hh:mm" timezone
                startdate = startdate.replace(hour=8)  # Set 8 AM in localtime
                startdate = startdate.astimezone(pytz.utc)  # Convert to UTC
                value['start_datetime'] = datetime.strftime(startdate, DEFAULT_SERVER_DATETIME_FORMAT)
            elif start:
                value['start_datetime'] = start

            if endtime:
                end = datetime.strptime(endtime.split(' ')[0], DEFAULT_SERVER_DATE_FORMAT)
                enddate = tz.localize(end).replace(hour=18).astimezone(pytz.utc)

                value['stop_datetime'] = datetime.strftime(enddate, DEFAULT_SERVER_DATETIME_FORMAT)
            elif end:
                value['stop_datetime'] = end
        if not value.get('value'):
            value['value'] = {}
        start = value['value'].get('start') or start
        if start:
            value['value']['week_number'], value['value']['weekday'] = self._change_week_and_weekday(start)
        return {'value': value}

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

    #~ @api.model
    #~ def weeks_list(self, present_ids, domain, **kwargs):
        #~ folded = {key: (key in self.FOLDED_WEEK) for key, _ in self.WEEKS}
        #~ return self.WEEKS[:], folded

    #~ _group_by_full = {
        #~ 'week_number': weeks_list,
    #~ }

    #~ def _read_group_fill_results(self, cr, uid, domain, groupby,
                                 #~ remaining_groupbys, aggregated_fields,
                                 #~ count_field, read_group_result,
                                 #~ read_group_order=None, context=None):
        #~ """
        #~ The method seems to support grouping using m2o fields only,
        #~ while we want to group by a week_number field.
        #~ Hence the code below - it replaces simple week_number values
        #~ with (value, name) tuples.
        #~ """
        #~ if groupby == 'week_number':
            #~ WEEK_DICT = dict(self.WEEKS)
            #~ for result in read_group_result:
                #~ week = result['week_number']
                #~ result['week_number'] = (week, WEEK_DICT.get(week))
        #~ return super(calendar_event, self)._read_group_fill_results(
            #~ cr, uid, domain, groupby, remaining_groupbys, aggregated_fields,
            #~ count_field, read_group_result, read_group_order, context
        #~ )
