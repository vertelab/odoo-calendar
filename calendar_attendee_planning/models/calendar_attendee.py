# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import datetime
from odoo.osv import expression
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError
import pytz
import numpy as np

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
    hr_leave_id = fields.Many2one(comodel_name='hr.leave')


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
        if len(new_overlap) != 0:
            self.set_state(new_overlap)
        if old_overlap:
            self.set_state(old_overlap,True)
        
        return res


    def set_state(self, overlapping_events,old=False):
        own_state = 'accepted'
        msg_1 = _('Attendee is already scheduled on another contracted calendar event that overlaps the current time.')
        msg_2 = _('Attendee is already scheduled on another regular calendar event that overlaps the current time.')
        msg_3 = _('Attendee is on leave and cannot be scheduled on events in the current time period.')
        msg_4 = _('Attendee is on leave and cannot be scheduled on events in the current time period. Attendee is also scheduled on another contracted calendar event that overlaps the current time.')
        msg_5 = _('Attendee is on leave and cannot be scheduled on events in the current time period. Attendee is also scheduled on another regular calendar event that overlaps the current time.')
        msg_6 = _('Attendee cannot be scheduled on hours outside of his/her work schedule.')
        msg_7 = _('Attendee cannot be scheduled on hours outside of his/her work schedule. Attendee is also scheduled on another contracted calendar event that overlaps the current time.')
        msg_8 = _('The scheduled time overlaps with the attendees lunch period.')

        if overlapping_events:
            for event in overlapping_events:
                for attendee_event in event.attendee_ids:
                    if attendee_event.id:

                        if attendee_event.state != 'declined':
                            if attendee_event.time_off():
                                attendee_event.write({'state': 'declined','state_msg': msg_4})
                            else:
                                attendee_event.write({'state': 'declined','state_msg': msg_1})

                        elif attendee_event.state_msg == msg_3:
                            attendee_event.state_msg = msg_4
                        
                        elif attendee_event.state_msg == msg_6:
                            attendee_event.state_msg = msg_7

                        elif old:
                            if attendee_event.state == 'declined':
                                attendee_event.write({'state': 'accepted','state_msg': ''})
                                #attendee_event.state = 'accepted'

                        if own_state != 'declined':
                            own_state = 'declined'

                    else:
                        if own_state != 'declined':
                            own_state = 'tentative'


            if self.work_interval() and own_state == 'declined' and self.state != 'declined':
                self.write({'state': 'declined','state_msg': msg_1})

            elif own_state == 'tentative' and self.state != 'tentative':
                self.write({'state': 'tentative','state_msg': msg_2})

        elif not self.time_off() and self.work_interval() and self.state != 'accepted':
            self.write({'state': 'accepted','state_msg': ''})

        if not self.work_interval() and not self.time_off():
            if self.lunch_period() and not self.time_off() and self.state_msg != msg_8 and own_state != 'declined':
                self.write({'state': 'tentative','state_msg': msg_8})
            elif not self.lunch_period() and self.state != 'declined':
                self.write({'state': 'declined','state_msg': msg_6})
            elif self.state == 'declined' and own_state != 'declined' and self.state_msg != msg_6:
                self.state_msg = msg_6
            
            if own_state == 'declined' and self.state_msg != msg_7 and not self.lunch_period():
                self.state_msg = msg_7
            elif own_state == 'declined' and self.state_msg != msg_1 and self.lunch_period():
                self.write({'state': 'declined','state_msg': msg_1})
        
        elif self.time_off():
            if self.state != 'declined':
                self.write({'state': 'declined','state_msg': msg_3})
            elif self.state == 'declined' and own_state != 'declined' and self.state_msg != msg_3:
                self.state_msg = msg_3

            if own_state == 'declined' and self.state_msg != msg_4:
                self.state_msg = msg_4
            elif own_state == 'tentative' and self.state_msg != msg_5:
                self.state_msg = msg_5


    def check_overlapping(self):
        overlapping_events = []
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


    def time_off(self):
        for participant in self:

            leaves = self.env['hr.leave'].search([
               ('employee_id.user_partner_id.id','=',participant.partner_id.id),
            ])

            declined = False
            for leave in leaves:
                if self.event_date_start > leave.date_from:
                    if self.event_date_start < leave.date_to:
                        declined = True
                elif self.event_date_end > leave.date_from:
                    if self.event_date_end < leave.date_to:
                        declined = True
                elif self.event_date_start >= leave.date_from:
                    if self.event_date_end <= leave.date_to:
                        declined = True
                elif self.event_date_start <= leave.date_from:
                    if self.event_date_end >= leave.date_to:
                        declined = True
                
                if declined == True:
                    return True
            return False


    def work_interval(self):
        current_tz = pytz.timezone('UTC')
        for participant in self:
            try:
                work_intervals = participant.partner_id.user_ids[0].employee_id[0].resource_calendar_id[0]._work_intervals(participant.event_date_start.astimezone(current_tz), 
                                                                                                                            participant.event_date_end.astimezone(current_tz))

                if work_intervals._items:
                    interval_start = work_intervals._items[0][0]
                    interval_stop = work_intervals._items[0][1]

                    if self.event_date_start.astimezone(current_tz) == interval_start and self.event_date_end.astimezone(current_tz) == interval_stop:
                        return True
                    else:
                        return False
                else:
                    return False
            except IndexError:
                continue

    def lunch_period(self):
        try:
            tz = self.partner_id.user_ids[0].employee_id.resource_calendar_id.tz
        except IndexError:
            return
        current_tz = pytz.timezone(tz)
        eventstart = self.event_date_start.astimezone(current_tz)
        eventend = self.event_date_end.astimezone(current_tz)
        data = {'0': {},'1': {},'2': {},'3': {},'4': {},'5': {},'6': {}}

        for period in self.partner_id.user_ids[0].employee_id[0].resource_calendar_id[0].attendance_ids:
            entry = data[period.dayofweek]
            entry[period.day_period] = (period.hour_from,period.hour_to)
            data[period.dayofweek] = entry
        dayofweek = eventstart.now().weekday()
        entry = data[str(dayofweek)]

        if len(entry) == 2:
            if 'morning' in entry and 'afternoon' in entry:
                if entry['morning'][1] != entry['afternoon'][0]:
                    day_start = entry['morning'][0]
                    lunch_start = entry['morning'][1]
                    lunch_stop = entry['afternoon'][0]
                    day_stop = entry['afternoon'][1]

                    # Convert eventstart hour and minute to a decimal integer
                    h_int = lambda e: int(e.time().strftime('%-H'))
                    m_int = lambda e: int(e.time().strftime('%-M')) / 60
                    eventstart_int = h_int(eventstart) + m_int(eventstart)
                    eventend_int = h_int(eventend) + m_int(eventend)

                    # Check if event time and lunch overlaps
                    if eventstart_int >= day_start and eventend_int <= day_stop:
                        if eventstart_int < lunch_start and eventend_int > lunch_start:
                            return True
                        elif eventstart_int < lunch_stop and eventend_int > lunch_stop:
                            return True
                        elif eventstart_int <= lunch_start and eventend_int >= lunch_stop:
                            return True
                        elif eventstart_int >= lunch_start and eventend_int <= lunch_stop:
                            return True
        return False

    def test(self):
        # ('partner_id','=',self.partner_id.id),
        mysearch = self.search([('event_date_start','>=',datetime.now())])
        _logger.warning(f"{mysearch=}")
        for record in mysearch:
            overlap = record.check_overlapping()
            self.set_state(overlap)
