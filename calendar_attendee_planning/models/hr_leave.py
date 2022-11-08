# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class HRLeaveWriteModify(models.Model):
    _inherit = "hr.leave"

    def write(self, vals):
        res = super().write(vals)
        
        return res