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

        partner_id = res.employee_id.user_partner_id.id
        my_overlap = self.check_overlapping()
        for overlap in my_overlap:
            for attendee in overlap.attendee_ids:
                attendee.set_state()
                    
        return res

    def check_overlapping(self):
        overlapping_events = self.env['calendar.event'].search([
                '&',
                '|',
                '&',
                ('start','<',self.date_from),
                ('stop','>',self.date_from),
                '|',
                '&',
                ('start','<',self.date_to),
                ('stop','>',self.date_to),
                '|',
                '&',
                ('start','<=',self.date_from),
                ('stop','>=',self.date_to),
                '&',
                ('start','>=',self.date_from),
                ('stop','<=',self.date_to),
                #('partner_id', 'in', attendee_partners),
                ('partner_id', '=', self.employee_id.user_partner_id.id),
                ])
        return overlapping_events

    def write(self, vals):
        #partner_id = self.employee_id.user_partner_id.id
        pre_move_overlap = self.check_overlapping()

        res = super().write(vals)

        post_move_overlap = self.check_overlapping()

        for overlap in pre_move_overlap:
            for attendee in overlap.attendee_ids:
                attendee.set_state()

        for overlap in post_move_overlap:
            for attendee in overlap.attendee_ids:
                attendee.set_state()

        return res
    
    def unlink(self):
        #partner_id = self.employee_id.user_partner_id.id
        pre_move_overlap = self.check_overlapping()

        res = super().unlink()

        for overlap in pre_move_overlap:
            for attendee in overlap.attendee_ids:
                attendee.set_state()

        return res
