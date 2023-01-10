# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import datetime
from odoo.osv import expression
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError
import pytz
import numpy as np
from copy import copy

_logger = logging.getLogger(__name__)

class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"
    _rec_name = 'event_id'

    @api.model
    def _show_all_partners(self,stages,domain,order):
        partners = self.env['res.partner']
        manager_children = [partner.user_partner_id for partner in self.env.user.employee_id.child_ids if partner.user_partner_id is not False]
        for partner in manager_children:
            partners += partner

        return partners

    user_id = fields.Many2one(related='event_id.user_id', store=True, group_expand='_read_attendee_ids', readonly=False)
    event_date_start = fields.Datetime(related='event_id.start', readonly=False)
    event_date_end = fields.Datetime(related='event_id.stop', readonly=False)
    event_week = fields.Char(compute='_compute_week_number', store=True, readonly=False)
    duration = fields.Float(related="event_id.duration", readonly=False)
    color = fields.Integer(compute='_compute_color_from_state', store=True, readonly=False)
    state_msg = fields.Char(string="Status message",)
    attendee_id = fields.Many2one(comodel_name='res.partner', store=True, readonly=False)
    # is_during_contract = fields.Boolean(compute="_check_if_during_contract", store=True)
    partner_id = fields.Many2one('res.partner', 'Contact', required=True, readonly=False, group_expand='_show_all_partners')
    # partner_skill_ids = fields.Many2many(related='partner_id.skill_ids', readonly=False)
    # partner_allergy_ids = fields.Many2many(related='partner_id.allergy_ids', readonly=False)


    # @api.depends('event_date_start')
    # def _check_if_during_contract(self):
    #     for rec in self:
    #         if not (isinstance(rec.contract_id.date_end, date) or isinstance(rec.contract_id.date_start, date)):
    #             _logger.warning(f"date_end is bool")
    #             break
        
    #         if rec.event_date_start.date() <= rec.contract_id.date_end and rec.contract_id.date_start <= rec.event_date_end.date():
    #             rec.state = 'accepted'
    #         else:
    #             rec.state = 'declined'
                # _logger.warning(f"{type(rec.event_date_start)} {type(rec.contract_id.date_end)}")
# if leave['request_date_from'] <= (event.start + datetime.timedelta(hours=event.duration)).date() and event.start.date() <= leave['request_date_to']:

    # @api.onchange('user_id.employee_id.leaves')
    # @api.depends('user_id.employee_id.leaves')
    # def _change_state_from_hr_leaves(self):
    #     _logger.warning(f"BAPIDI ")

    @api.depends('state')
    def _compute_color_from_state(self):
        for rec in self:
            if rec.state == 'declined':
                rec.color = 1
            elif rec.state == 'accepted':
                rec.color = 4
                rec.state_msg=''
            elif rec.state == 'tentative':
                rec.color = 2

    @api.depends('event_date_start')
    def _compute_week_number(self):
        for rec in self:
            # _logger.warning(f"FIRST: {date.today().year} SECOND: {datetime.date(rec.event_date_start).isocalendar()[1]} THIRD: {datetime.strptime('%s-%s-%s' % (date.today().year, datetime.date(rec.event_date_start).isocalendar()[1], 1), '%G-%V-%u')} FOURTH: {datetime.strptime('%s-%s-%s' % (date.today().year, datetime.date(rec.event_date_start).isocalendar()[1], 1), '%G-%V-%u').strftime('%Y-%m-%d')}")
            rec.event_week = datetime.strptime('%s-%s-%s' % (date.today().year, datetime.date(rec.event_date_start).isocalendar()[1], 1), '%G-%V-%u').strftime('%Y-%m-%d')
            # rec.event_week = datetime.date(rec.event_date_start).isocalendar()[1]

    # @api.depends('event_id.start', 'event_id.stop')
    # def _check_employee_availability_date_leaves(self):
    #     for rec in self:
    #         _logger.warning(f"hewwo {rec}")

    # @api.onchange('partner_id')
    # def _check_employee_availability_partner_id(self):
    #     for rec in self:
    #         _logger.warning(f"hewwo {rec}")
        
    def _read_attendee_ids(self, custom, domain, order):
        employees = self.env['res.users'].search([])
        return employees
        
    def write(self, vals):

        old_overlap = None
        if 'event_date_start' in vals:
            old_overlap = self.check_overlapping()

        res = super().write(vals)
        new_overlap = self.check_overlapping()
        self.set_state(new_overlap)
        if old_overlap:
            self.set_state(old_overlap,True)
        


        # if vals.get('partner_id',) or vals.get('event_date_start',):
        #     for participant in self.event_id.attendee_ids:
        #         # _logger.warning(f"self print {self} {self.partner_id}")
        #         write_state = 'accepted'

        #         partner = self.env['res.partner'].browse(participant.partner_id.id)
        #         #fix error that triggers when partner does not have employee id
        #         try:
        #             employee_id = partner.user_ids[0].employee_id[0].id
        #         except IndexError:
        #             # _logger.warning('hello')
        #             raise UserError('Attendee must be an employee')

        #         leave_periods = self.env['hr.leave'].search([('employee_id', '=', employee_id)]).ids
        #         _logger.warning(f"leave_periods: {leave_periods}")

        #         for leave_id in leave_periods:
        #             leave = self.env['hr.leave'].browse(leave_id)
        #             # try:
        #             if leave.date_from <= participant.event_date_end and participant.event_date_start <= leave.date_to:
        #                 participant.write({'state': 'declined'})
        #                 write_state = 'declined'
        #                 _logger.warning("Checkpoint Alpha declined write")
        #                 break
        #             else:
        #                 participant.write({'state': 'accepted'})
        #                 _logger.warning("Checkpoint Alpha accepted write")

        #         if write_state != 'declined':
        #             # declined_count = 0
        #             # for day in workdays:        
        #             #     # _logger.warning(f"for loop {day.dayofweek} {today_int}")
        #             #     if int(day.dayofweek) == int(today_int): 
        #             #         time_hour_from = datetime.strptime(str(int(day.hour_from)), '%H').time()
        #             #         time_hour_to = datetime.strptime(str(int(day.hour_to)), '%H').time()
        #             #         # _logger.warning(f" {time_hour_from} {time_hour_to}")

        #             #         # _logger.warning(f"{time_hour_from} {time_hour_to}")
        #             #         if self.event_date_start.time() >= time_hour_from and self.event_date_end.time() <= time_hour_to:
        #             #             # _logger.warning('inside the last if')
        #             #             self.write({'state': 'accepted'})
        #             #             break
        #             #         else:
        #             #             self.write({'state': 'declined'})
        #             #             declined_count += 1
        #             # if declined_count == 2:
        #             #     write_state = 'declined'

        #             # workday_length = partner.user_ids[0].employee_id[0].resource_calendar_id.hours_per_day
        #             current_tz = pytz.timezone('UTC')
        #             workdays = partner.user_ids[0].employee_id[0].resource_calendar_id.attendance_ids
        #             event_day = participant.event_date_start.weekday()

        #             _logger.warning(f"workdays: {workdays}")

        #             work_intervals = partner.user_ids[0].employee_id[0].resource_calendar_id[0]._work_intervals(participant.event_date_start.astimezone(current_tz), 
        #                                                                                                         participant.event_date_end.astimezone(current_tz))
        #             _logger.warning(f"work_intervals: {work_intervals._items}")                                                                                                           
                    
        #             if len(work_intervals._items) != 0:
        #                 acceptable_count = 0
        #                 for count, interval in enumerate(work_intervals._items[0]):
        #                     _logger.warning(count)
        #                     _logger.warning(interval)
        #                     if count == 0:
        #                         # _logger.warning(f"Timezone shenanigans incoming {self.event_date_start} {interval} {current_tz.localize(self.event_date_start) >= interval} {current_tz.localize(self.event_date_end) <= interval}")
        #                         if current_tz.localize(participant.event_date_start) >= interval:
        #                             acceptable_count += 1
        #                             _logger.warning("A")
        #                             continue

        #                     if count == 1:
        #                         # _logger.warning(f"Timezone shenanigans incoming {self.event_date_start} {interval} {current_tz.localize(self.event_date_start) >= interval} {current_tz.localize(self.event_date_end) <= interval}")
        #                         if current_tz.localize(participant.event_date_end) <= interval:
        #                             acceptable_count += 1
        #                             _logger.warning("B")
        #                             continue

        #                 # _logger.warning(f"{acceptable_count}")
        #                 if acceptable_count != 0:
        #                     filtered = list(filter(lambda day: int(day.dayofweek) == int(event_day), workdays))
        #                     # _logger.warning(f"WORKDAYS: {workdays}")
        #                     # _logger.warning(f"event_day: {event_day}")
        #                     # for day in workdays:
        #                     #     _logger.warning(f"DAYOFWEEK: {day.dayofweek}")
        #                     # _logger.warning(f"ATTENDEE CREATE FILTERED: {filtered}")
        #                     # _logger.warning(self.event_date_start.hour)
        #                     # _logger.warning(filtered[0].hour_to)
        #                     # _logger.warning(self.event_date_end.hour)
        #                     # _logger.warning(filtered[1].hour_from)
        #                     try:
        #                         hour_to_datetime = current_tz.localize(participant.event_date_start.replace(hour=int(filtered[0].hour_to)))
        #                         hour_from_datetime = current_tz.localize(participant.event_date_end.replace(hour=int(filtered[0].hour_from)))
        #                     except IndexError:
        #                         raise UserWarning('hour_to_datetime is pointing at empty list')
        #                     # _logger.warning(f"Timezone shenanigans IF {hour_to_datetime} {hour_from_datetime}")
        #                     if acceptable_count == 2:
        #                         participant.write({'state': 'accepted'})
        #                         write_state = 'accepted'
        #                         _logger.warning("Checkpoint Zetta accepted write")
        #                     elif acceptable_count == 1:
        #                         participant.write({'state': 'tentative'})
        #                         write_state = 'tentative'
        #                         _logger.warning("Checkpoint Zettea tentative write")
        #                     # else:
        #                     #     self.write({'state': 'declined'})
        #                     #     write_state = 'declined'
        #                     #     # _logger.warning("E")
        #                 else:
        #                     participant.write({'state': 'declined'})
        #                     write_state = 'declined'
        #                     _logger.warning("Checkpoint Beta declined write")
        #             else:
        #                 # _logger.warning(current_tz.localize(self.event_date_start))
        #                 # filtered = list(filter(lambda day: int(day.dayofweek) == int(event_day), workdays))

        #                 participant.write({'state': 'declined'})
        #                 write_state = 'declined'
        #                 _logger.warning("Checkpoint Gamma declined write")
        #                 # _logger.warning(f"F {write_state}")

        #     # attendee_ids = self.event_id.attendee_ids
        #     # ID = self.id            
        #     # if not self.env.context.get('dont_write'):
        #     #     for attendee_id in attendee_ids:                    attendee_id.with_context({'dont_write': True}).write({'state': write_state})

        # # _logger.warning(f' BYPIDI WRITE {self} {vals} {res}')
        return res


    def set_state(self, overlapping_events,old=False):

        own_state = 'accepted'
        declined = {
                    'state': 'declined',
                    'state_msg': 'Attendee is already booked on a contracted calendar event within the same time frame.'
                    }
        tentative = {
                    'state': 'tentative',
                    'state_msg': 'Attendee is already booked on a regular calendar event within the same time frame.'
                    }

        if overlapping_events:
            for event in overlapping_events:

                if event.attendee_ids.id:

                    if event.attendee_ids.state != 'declined':
                        event.attendee_ids.write(declined)

                    elif old:
                        if event.attendee_ids.state == 'declined':
                            event.attendee_ids.state = 'accepted'

                    if own_state != 'declined':
                        own_state = 'declined'

                else:
                    if own_state != 'declined':
                        own_state = 'tentative'

            if own_state == 'declined' and self.state != 'declined':
                self.write(declined)

            elif own_state == 'tentative' and self.state != 'tentative':
                self.write(tentative)

        elif self.state != 'accepted':
            self.state = 'accepted'


    def check_overlapping(self):
        for participant in self:
            overlapping_events = self.env['calendar.event'].search([
                    '&',
                    '|',
                    '&',
                    ('start','<',self.event_date_start),
                    ('stop','>',self.event_date_start),
                    '|',
                    '&',
                    ('start','<',self.event_date_end),
                    ('stop','>',self.event_date_end),
                    '|',
                    '&',
                    ('start','<=',self.event_date_start),
                    ('stop','>=',self.event_date_end),
                    '&',
                    ('start','>=',self.event_date_start),
                    ('stop','<=',self.event_date_end),
                    '&',
                    #('partner_id', 'in', attendee_partners),
                    ('partner_id', '=', participant.partner_id.id),
                    ('id', '!=', self.event_id.id),
                    ])
        return overlapping_events
