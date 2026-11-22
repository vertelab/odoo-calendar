# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)

class HrEmployeeWriteModify(models.Model):
    _inherit = "hr.employee"

    def write(self,vals):
        res = super().write(vals)
        if 'hr.contract' in self:
            if 'resource_calendar_id' in vals:
                events = self.env['calendar.attendee'].search([('event_date_start','>=',datetime.now()),('partner_id','=',self.user_partner_id.id)])
                for event in events:
                    overlap = event.check_overlapping()
                    event.set_state(overlap)

        return res
