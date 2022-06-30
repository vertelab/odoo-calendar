import logging
from odoo import fields, models, api, _
_logger = logging.getLogger(__name__)

class ResCalendarSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ics_url = fields.Char(string='Enter the URL of the ICS file')

    def test(self):
        _logger.warning("test")