# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class HREmployeeLeave(models.Model):
    _inherit = "hr.employee"

    leaves = fields.One2many('hr.leave', 'employee_id', store=True)