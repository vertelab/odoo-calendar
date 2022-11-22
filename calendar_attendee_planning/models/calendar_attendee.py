# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import datetime
from datetime import date, datetime

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
            partner = self.env['res.partner'].browse(self.partner_id.id)
            employee_id = partner.user_ids[0].employee_id[0].id

            leave_periods = self.env['hr.leave'].search([('employee_id', '=', employee_id)]).ids

            for leave_id in leave_periods:
                leave = self.env['hr.leave'].browse(leave_id)
                # try:
                if leave.date_from <= self.event_date_end and self.event_date_start <= leave.date_to:
                    self.write({'state': 'declined'})
                    break
                else:
                    self.write({'state': 'accepted'})

        _logger.warning(f' BYPIDI WRITE {self} {vals} {res}')
        return res