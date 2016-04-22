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

class calendar_event(models.Model):
    _inherit = 'calendar.event'

    color = fields.Integer(string='Color Index')
    week_number = fields.Char(string='Week number', compute='_get_week_number')
    day = fields.Char(compute='_get_day')

    @api.one
    @api.depends('start_date')
    def _get_week_number(self):
        self.week_number = fields.Date.from_string(self.start_date) and fields.Date.from_string(self.start_date).isocalendar()[1]
        #~ if self.start_date:
            #~ date = fields.Date.from_string(self.start_date)
            #~ self.week_number = date and date.isocalendar()[1] or ''
            #~ self.week_number = self.start_date


    #~ def _set_week_number(self):
        #~ self.write({'week_number': time.strftime('%W')})

    @api.depends('start_date')
    @api.one
    def _get_day(self):
        self.day = self.start_date and self.start_date[:6] or ''

    #~ def _set_day(self):
        #~ self.write({'start_datetime': time.strftime("%D %H:%M:%S")})
