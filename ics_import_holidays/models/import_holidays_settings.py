from ast import Store
import logging
from multiprocessing.sharedctypes import Value
from odoo import fields, models, api, _
import time

_logger = logging.getLogger(__name__)
IMPORT = '__import__'

class ResCalendarSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ics_url = fields.Char(string='Enter the URL of the ICS file', config_parameter='holiday.url.ics',)

    def test_ics_url(self):
        _logger.warning(self.ics_url)
        
    @api.model
    def create(self, vals_list):
        res = super().create(vals_list)
        
        if (ics_url := vals_list.get("ics_url")):
            ics_xmlid = f"{IMPORT}.ics_{time.strftime('%Y-%m-%d_%H:%M:%S')}_{ics_url.replace('.','_')}"
            try:
                ref_try = self.env.ref(ics_xmlid)  
            except ValueError:
                external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                    'name': ics_xmlid.split('.')[-1], 
                                    'model': 'ir.cron'})                               

                self.env['ir.cron'].create([{'name': 'Update holidays URL: ' + ics_url,
                                        'model_id': 330, 'user_id': 2, 'interval_number': 1,  
                                        'interval_type': 'months', 'code': 'model._holiday_cron()', 
                                        'numbercall': -1}]) 
        else:
            _logger.warning(f"{vals_list}")

        return res