from ast import Store
import logging
from multiprocessing.sharedctypes import Value
from odoo import fields, models, api, _
import time
import requests

_logger = logging.getLogger(__name__)
IMPORT = '__import__'

class ResCalendarSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ics_url = fields.Char(string='Enter the URL of the ICS file', config_parameter='holiday.url.ics')
        
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

                cron_name = 'Update holidays URL: ' + ics_url
                calendar_event_cron_model = self.env['ir.model'].search([('model', '=', 'calendar.event')]).id

                if not self.env['ir.cron'].search([('name', '=', cron_name)]):
                    self.env['ir.cron'].create([{'name': cron_name,
                                            'model_id': calendar_event_cron_model, 'user_id': 2, 'interval_number': 1,  
                                            'interval_type': 'months', 'code': 'model._holiday_cron()', 
                                            'numbercall': -1}])

                if not self.env['res.users'].search([('login', '=', "holidays")]):
                    self.env['res.users'].sudo().create({'name': "Holidays", 'login': "holidays"})
        return res
    
    