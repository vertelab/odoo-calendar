# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import datetime
from datetime import date, datetime, timedelta
import pytz
import numpy as np

_logger = logging.getLogger(__name__)

class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"
    _rec_name = 'event_id'

    user_id = fields.Many2one(related='event_id.user_id', store=True, group_expand='_read_attendee_ids', readonly=False)
    event_date_start = fields.Datetime(related='event_id.start', store=True, readonly=False)
    event_date_end = fields.Datetime(related='event_id.stop', readonly=False)
    event_week = fields.Char(compute='_compute_week_number', store=True, readonly=False)
    duration = fields.Float(related="event_id.duration", readonly=False)
    color = fields.Integer(compute='_compute_color_from_state', store=True, readonly=False)
    attendee_id = fields.Many2one(comodel_name='res.partner', store=True, readonly=False)
    # is_during_contract = fields.Boolean(compute="_check_if_during_contract", store=True)
    partner_id = fields.Many2one('res.partner', 'Contact', required=True, readonly=False)
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

        res = super(CalendarAttendee, self).write(vals)
        if vals.get('partner_id',) or vals.get('event_date_start',):
            write_state = 'accepted'

            partner = self.env['res.partner'].browse(self.partner_id.id)
            #fix error that triggers when partner does not have employee id
            employee_id = partner.user_ids[0].employee_id[0].id

            leave_periods = self.env['hr.leave'].search([('employee_id', '=', employee_id)]).ids

            for leave_id in leave_periods:
                leave = self.env['hr.leave'].browse(leave_id)
                # try:
                if leave.date_from <= self.event_date_end and self.event_date_start <= leave.date_to:
                    self.write({'state': 'declined'})
                    write_state = 'declined'
                    break
                else:
                    self.write({'state': 'accepted'})



            if write_state != 'declined':
                # declined_count = 0
                # for day in workdays:        
                #     # _logger.warning(f"for loop {day.dayofweek} {today_int}")
                #     if int(day.dayofweek) == int(today_int): 
                #         time_hour_from = datetime.strptime(str(int(day.hour_from)), '%H').time()
                #         time_hour_to = datetime.strptime(str(int(day.hour_to)), '%H').time()
                #         # _logger.warning(f" {time_hour_from} {time_hour_to}")

                #         # _logger.warning(f"{time_hour_from} {time_hour_to}")
                #         if self.event_date_start.time() >= time_hour_from and self.event_date_end.time() <= time_hour_to:
                #             # _logger.warning('inside the last if')
                #             self.write({'state': 'accepted'})
                #             break
                #         else:
                #             self.write({'state': 'declined'})
                #             declined_count += 1
                # if declined_count == 2:
                #     write_state = 'declined'

                # workday_length = partner.user_ids[0].employee_id[0].resource_calendar_id.hours_per_day
                workdays = partner.user_ids[0].employee_id[0].resource_calendar_id.attendance_ids
                today_int = datetime.today().weekday()
                work_intervals = partner.user_ids[0].employee_id[0].resource_calendar_id[0]._work_intervals(self.event_date_start.astimezone(pytz.timezone('UTC')), 
                                                                                                            self.event_date_end.astimezone(pytz.timezone('UTC')))

                current_tz = pytz.timezone('UTC')
                if len(work_intervals._items) != 0:
                    state_bool = True
                    for count, interval in enumerate(work_intervals._items[0]):
                        # _logger.warning(count)
                        # _logger.warning(interval)
                        if count == 0:
                            if current_tz.localize(self.event_date_start) >= interval:
                                # _logger.warning("A")
                                continue
                            else:
                                state_bool = False
                                # _logger.warning("B")
                                # _logger.warning(current_tz.localize(self.event_date_start))
                                # _logger.warning(interval)
                                break

                        if count == 1:
                            if current_tz.localize(self.event_date_end) <= interval:
                                # _logger.warning("C")
                                continue
                            else:
                                # _logger.warning("D")
                                state_bool = False
                                break

                    if not state_bool:
                        filtered = list(filter(lambda day: int(day.dayofweek) == int(today_int), workdays))
                        # _logger.warning(self.event_date_start.hour)
                        # _logger.warning(filtered[0].hour_to)
                        # _logger.warning(self.event_date_end.hour)
                        # _logger.warning(filtered[1].hour_from)
                        hour_to_datetime = current_tz.localize(self.event_date_start.replace(hour=int(filtered[0].hour_to)))
                        hour_from_datetime = current_tz.localize(self.event_date_end.replace(hour=int(filtered[0].hour_from)))
                        if current_tz.localize(self.event_date_start) <= hour_to_datetime:
                            self.write({'state': 'tentative'})
                            write_state = 'tentative'
                        else:
                            self.write({'state': 'declined'})
                            write_state = 'declined'
                            # _logger.warning("E")
                else:
                    # _logger.warning(current_tz.localize(self.event_date_start))
                    # filtered = list(filter(lambda day: int(day.dayofweek) == int(today_int), workdays))

                    self.write({'state': 'declined'})
                    write_state = 'declined'
                    # _logger.warning(f"F {write_state}")

            attendee_ids = self.event_id.attendee_ids
            ID = self.id            
            if not self.env.context.get('dont_write'):
                for attendee_id in attendee_ids:
                    attendee_id.with_context({'dont_write': True}).write({'state': write_state})

        # _logger.warning(f' BYPIDI WRITE {self} {vals} {res}')
        return res