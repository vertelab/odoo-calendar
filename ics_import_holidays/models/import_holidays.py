# -*- coding: utf-8 -*-
from base64 import b64decode
import datetime
from modulefinder import IMPORT_NAME
from multiprocessing.sharedctypes import Value
from odoo import fields, models, api, _
import logging
from ics import Calendar, Event
import requests

_logger = logging.getLogger(__name__)
IMPORT = '__import__'

class ImportHolidays(models.Model):
    _inherit = 'calendar.event'

    @api.model
    def _holiday_cron(self):       
        url = self.env['ir.config_parameter'].sudo().get_param('holiday.url.ics')
        calendar = Calendar(requests.get(url).text)
        responsible_id = self.env['res.users'].search([('login', '=', 'holidays')])[0].id

        for event in list(calendar.timeline): 
            event_xmlid = f"{IMPORT}.calendar_{event.name.replace(' ', '_')}_{event.begin.date().strftime('%Y-%m-%d')}"
            try:
                ref_try = self.env.ref(event_xmlid)

            except ValueError: 
                event_id = self.env["calendar.event"].create({'name': event.name, 
                                                'start': event.begin.date().strftime('%Y-%m-%d'), 
                                                'stop': event.begin.date().strftime('%Y-%m-%d'), 'allday': 'True',
                                                'user_id': responsible_id})

                external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                                'name': event_xmlid.split('.')[-1], 
                                                'model': 'calendar.event',
                                                'res_id': event_id.id})                               
                
            for resource_calendar in self.env['resource.calendar'].search_read([], ['id', 'hours_per_day']):  
                hours_week = (resource_calendar['hours_per_day'] * 5)
                uid = f"{hours_week}_{event.name.replace(' ', '_')}_{event.begin.date().strftime('%Y-%m-%d')}".replace('.','_')
                leave_xmlid = f"{IMPORT}.leaves_{uid}"
              
                try:
                    ref_try = self.env.ref(leave_xmlid)

                except ValueError: 
                    leave_id = self.env["resource.calendar.leaves"].create({'name': event.name,
                                                    'calendar_id': resource_calendar['id'], 
                                                    'date_from': (event.begin.date() - datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'), 
                                                    'date_to': (event.begin.date() + datetime.timedelta(hours=22)).strftime('%Y-%m-%d %H:%M:%S')
                                                    })

                    external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                                    'name': leave_xmlid.split('.')[-1], 
                                                    'model': 'resource.calendar.leaves',
                                                    'res_id': leave_id.id})    