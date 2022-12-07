# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import datetime
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class HRLeaveWriteModify(models.Model):
    _inherit = "hr.leave"

    @api.model
    def create(self, vals_list):
        res = super().create(vals_list)
        # _logger.warning(vals_list)

        partner_id = res.employee_id.user_partner_id.id
        partner_in_attendees = self.env['calendar.attendee'].search([('partner_id', '=', partner_id)]).ids
        # _logger.warning(partner_in_attendees)
        for calendar_attendee_id in partner_in_attendees:
            attendee = self.env['calendar.attendee'].browse(calendar_attendee_id) 
            # _logger.warning(attendee)

            for rec in attendee:
                if rec.event_date_start <= res.date_to and res.date_from <= rec.event_date_end:
                    rec.write({'state': 'declined'})
                    
        return res

    def write(self, vals_list):
        res = super().write(vals_list)
        # _logger.warning(vals_list)

        partner_id = self.employee_id.user_partner_id.id
        partner_in_attendees = self.env['calendar.attendee'].search([('partner_id', '=', partner_id)]).ids
        # _logger.warning(partner_in_attendees)
        for calendar_attendee_id in partner_in_attendees:
            attendee = self.env['calendar.attendee'].browse(calendar_attendee_id) 
            # _logger.warning(attendee)

            for rec in attendee:
                if rec.event_date_start <= self.date_to and self.date_from <= rec.event_date_end:
                    rec.write({'state': 'declined'})
                    
        return res

    # def create(self, vals_list):
    #     res = super(HRLeaveWriteModify, self).create(vals_list)
    #     _logger.warning(f"HR LEAVE CREATE {res} {vals_list}")

    # def write(self, vals):
    #     res = super(HRLeaveWriteModify, self).write(vals)
    #     _logger.warning(f"HR LEAVE WRITE {res} {vals}")

    # @api.onchange('date_from', 'date_to', 'number_of_days')
    # @api.depends('date_from', 'date_to', 'number_of_days')
    # def update_calendar_attendees(self):
    #     _logger.warning('HELLO')
    #     for rec in self:
    #         partner_id = self.employee_id.user_partner_id.id
    #         calendar_attendees_ids = self.env['calendar.attendee'].search([('partner_id', '=', partner_id)])

    #         for id in calendar_attendees_ids:
    #             browse_attendee = self.env['calendar.attendee'].browse(id)
    #             _logger.warning(browse_attendee)
