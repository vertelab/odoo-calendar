from odoo import models, fields, api
import logging
import datetime
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"

    contract_skill_ids = fields.Many2many(related='contract_id.skill_ids', readonly=False)
    contract_allergy_ids = fields.Many2many(related='contract_id.allergy_ids', readonly=False)
    partner_skill_ids = fields.Many2many(related='partner_id.skill_ids', readonly=False)
    partner_allergy_ids = fields.Many2many(related='partner_id.allergy_ids', readonly=False)

    # @api.depends('partner_id')
    # def check_skills_allergies_match(self):
    #     _logger.warning(f"HELLO {self.contract_skill_ids.ids}")

    def write(self, vals):
        res = super().write(vals)
        if vals.get('partner_id',):
            # _logger.warning(self.contract_skill_ids.ids)
            # _logger.warning(self.partner_skill_ids.ids)
            # contract_skill_id_list = [x for x in self.contract_skill_ids.ids].sort()
            # partner_skill_id_list = [x for x in self.partner_skill_ids.ids].sort()
            # _logger.warning(contract_skill_id_list)
            # _logger.warning(partner_skill_id_list)

            if not all(skill in self.partner_skill_ids.ids for skill in self.contract_skill_ids.ids):
                self.state = 'declined'

