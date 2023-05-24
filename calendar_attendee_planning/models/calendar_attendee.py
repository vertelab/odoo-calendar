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

    def _read_attendee_ids(self, custom, domain, order):
        employees = self.env['res.users'].search([])
        return employees
        

    # Creates a status message for an attendee, based on state_vals
    def status_msg(self,state_vals):
        attendee_overlap = _('Attendee is already scheduled on another contracted calendar event that overlaps the current time.')
        event_overlap = _('Attendee is already scheduled on another regular calendar event that overlaps the current time.')
        attendee_on_leave = _('Attendee is on leave and cannot be scheduled on events in the current time period.')
        #msg_4 = _('Attendee is on leave and cannot be scheduled on events in the current time period. Attendee is also scheduled on another contracted calendar event that overlaps the current time.')
        #msg_5 = _('Attendee is on leave and cannot be scheduled on events in the current time period. Attendee is also scheduled on another regular calendar event that overlaps the current time.')
        outside_work_hours = _('Attendee cannot be scheduled on hours outside of his/her work schedule.')
        #msg_7 = _('Attendee cannot be scheduled on hours outside of his/her work schedule. Attendee is also scheduled on another contracted calendar event that overlaps the current time.')
        attendee_on_lunch = _('The scheduled time overlaps with the attendees lunch period.')
        attendee_regular_overlap = _('Attendee is already scheduled on a regular calendar event that overlaps the current time.')

        msg = ''
        if state_vals['outside_work_hours']:
            msg = msg + ' ' + outside_work_hours
        if state_vals['attendee_overlapping']:
            msg = msg + ' ' + attendee_overlap
        if state_vals['attendee_on_leave']:
            msg = msg + ' ' + attendee_on_leave
        if state_vals['attendee_on_lunch']:
            msg = msg + ' ' + attendee_on_lunch
        if state_vals['event_overlapping']:
            msg = msg + ' ' + attendee_regular_overlap
        
        return msg


    # Updates the status message of attendee event
    def status_write(self, msg, tentative=False):
        if msg == '':
            state = 'accepted'
        elif tentative == True:
            state = 'tentative'
        else:
            state = 'declined'

        if self.state != state or self.state_msg != msg:
            self.write({'state': state,'state_msg': msg})

        return


    # Finds and sets the state of an attende event
    def set_state(self):
        if not self.check_attendee_from_contract():
            return
        # Checks all possible states
        state_vals = {}
        tentative = False
        state_vals['attendee_on_lunch'] = self.lunch_period()
        state_vals['outside_work_hours'] = not self.work_interval()
        state_vals['attendee_overlapping'] = self.check_overlapping()
        state_vals['attendee_on_leave'] = self.time_off()
        state_vals['event_overlapping'] = self.event_overlapping()

        if not state_vals['outside_work_hours'] and not state_vals['attendee_overlapping'] and not state_vals['attendee_on_leave']:
            if state_vals['event_overlapping']:
                tentative = True

        if state_vals['attendee_on_lunch']:
            state_vals['outside_work_hours'] = False
            if not state_vals['attendee_overlapping'] and not state_vals['attendee_on_leave']:
                tentative = True
        
        if state_vals['attendee_on_leave']:
            state_vals['event_overlapping'] = False
            state_vals['attendee_on_lunch'] = False


        # Creates status message and sets it
        msg = self.status_msg(state_vals)        
        self.status_write(msg, tentative)


    def event_overlapping(self):
        if not self.event_id:
            return False
        event = self.env['calendar.event'].browse(self.event_id.id)
        event_list = event.check_overlapping()
        for other_events in event_list:
            for attendee in other_events.partner_ids:
                if attendee == self.partner_id:
                    return True
        return False


    def check_overlapping(self):
        overlapping_events = []
        #for event in self:
        overlapping_events = self.env['calendar.attendee'].search([
                '&',
                    '|',
                        '&',
                            ('event_date_start','<',self.event_date_start),
                            ('event_date_end','>',self.event_date_start),
                        '|',
                            '&',
                                ('event_date_start','<',self.event_date_end),
                                ('event_date_end','>',self.event_date_end),
                            '|',
                                '&',
                                    ('event_date_start','<=',self.event_date_start),
                                    ('event_date_end','>=',self.event_date_end),
                                '&',
                                    ('event_date_start','>=',self.event_date_start),
                                    ('event_date_end','<=',self.event_date_end),
                    '&',
                        ('contract_id', '!=', False),
                        '&',
                            ('partner_id', '=', self.partner_id.id),
                            ('id', '!=', self.id),
                ])
        if overlapping_events:
            return True
        return False


    def check_attendee_from_contract(self):
        if self.contract_id:
            return True
        return False


    def time_off(self):
        for participant in self:

            leaves = self.env['hr.leave'].search([
                '&',
                    ('employee_id.user_partner_id.id','=',participant.partner_id.id),
                    ('state','=','validate')
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
                work_intervals = participant.partner_id.user_ids[0].employee_id.resource_calendar_id._work_intervals(participant.event_date_start.astimezone(current_tz), 
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
            except IndexError as e:
                _logger.error(f"{e=}")
                #continue


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


    def set_state_on_all_future_events(self):
        mysearch = self.search([('event_date_start','>=',datetime.now())])
        for record in mysearch:
            overlap = record.check_overlapping()
            self.set_state(overlap)
