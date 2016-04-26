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
        (next_six_weeks()[0], next_six_weeks()[0]),
        (next_six_weeks()[1], next_six_weeks()[1]),
        (next_six_weeks()[2], next_six_weeks()[2]),
        (next_six_weeks()[3], next_six_weeks()[3]),
        (next_six_weeks()[4], next_six_weeks()[4]),
        (next_six_weeks()[5], next_six_weeks()[5]),
    ]

    # which week shows folded by default
    FOLDED_WEEK = [
        next_six_weeks()[1],
        next_six_weeks()[2],
        next_six_weeks()[3],
        next_six_weeks()[4],
        next_six_weeks()[5],
    ]

    color = fields.Integer(string='Color Index')
    week_number = fields.Selection(WEEKS, string='Week number', inverse='set_week_day', readonly=True, store=True)

    @api.one
    def get_week_number(self):
        if self.allday:
            self.write({
                'week_number': str(fields.Date.from_string(self.start_date).isocalendar()[0]) + '-W' + str(fields.Date.from_string(self.start_date).isocalendar()[1]),
                })
        if not self.allday:
            self.write({
                'week_number': str(fields.Date.from_string(self.start_datetime).isocalendar()[0]) + '-W' + str(fields.Date.from_string(self.start_datetime).isocalendar()[1]),
            })

    @api.one
    def set_week_day(self):
        if self.allday:
            week_day = str(fields.Date.from_string(self.stop_date).weekday() + 1 if fields.Date.from_string(self.stop_date).weekday() < 6 else 0)
            self.write({
                'start_date': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + week_day, '%Y-W%W-%w')),
                'stop_date': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + week_day, '%Y-W%W-%w')),
            })
        if not self.allday:
            week_day = str(fields.Date.from_string(self.start_datetime).weekday() + 1 if fields.Date.from_string(self.start_datetime).weekday() < 6 else 0)
            meeting_start = str(fields.Datetime.from_string(self.start_datetime).hour) + ':' + str(fields.Datetime.from_string(self.start_datetime).minute) + ':' + str(fields.Datetime.from_string(self.start_datetime).second)
            meeting_stop = str(fields.Datetime.from_string(self.stop_datetime).hour) + ':' + str(fields.Datetime.from_string(self.stop_datetime).minute) + ':' + str(fields.Datetime.from_string(self.stop_datetime).second)
            self.write({
                'start_datetime': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + week_day, '%Y-W%W-%w')) + ' ' + meeting_start,
                'stop_datetime': fields.Date.to_string(datetime.datetime.strptime(self.week_number + '-' + week_day, '%Y-W%W-%w')) + ' ' + meeting_stop,
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
