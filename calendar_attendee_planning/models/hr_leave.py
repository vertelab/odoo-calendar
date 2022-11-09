# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class HRLeaveWriteModify(models.Model):
    _inherit = "hr.leave"

    # def create(self, vals_list):
    #     res = super(HRLeaveWriteModify, self).create(vals_list)
    #     _logger.warning(f"HR LEAVE CREATE {res} {vals_list}")

    # def write(self, vals):
    #     res = super(HRLeaveWriteModify, self).write(vals)
    #     _logger.warning(f"HR LEAVE WRITE {res} {vals}")