# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarEventModify(models.Model):
    _inherit = "calendar.event"

    def create(self, vals_list):
        res = super().create(vals_list)
        _logger.warning(f"BAPIDI {self} {vals_list} {res}")
        # _logger.warning(f"calendar event {self.env['calendar.event'].search_read([('id', '=', res.id)],[])}")
        return res
        
    def write(self, vals):
        res = super().write(vals)
        _logger.warning(f"BOPIDI {self} {vals} {res}")
        return res