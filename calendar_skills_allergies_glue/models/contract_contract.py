import datetime
import logging

from odoo import models, fields, api, _
from datetime import datetime, timedelta 

_logger = logging.getLogger(__name__)

class ContractSkillAllergy(models.Model):
    _inherit = "contract.contract"

    skill_ids = fields.Many2many('res.skill', string='Skills')
    allergy_ids = fields.Many2many('res.allergy', string='Allergies')     
