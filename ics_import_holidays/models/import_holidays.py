# -*- coding: utf-8 -*-
from base64 import b64decode
import datetime
from modulefinder import IMPORT_NAME
from multiprocessing.sharedctypes import Value
from unicodedata import name
from odoo import fields, models, api, _
import logging
from ics import Calendar, Event
import requests

_logger = logging.getLogger(__name__)
IMPORT = '__import__'

eves = {
    'Nyårsdagen' : 'Nyårsafton',
    'Påsk': 'Påskafton',
    'Midsommardagen': 'Midsommarafton',
    'Juldagen': 'Julafton',
}

<<<<<<< HEAD
=======
# https://www.helgdagar.nu/midsommar/midsommarafton-rod-dag


>>>>>>> ff40e74a4ea1dab77dafe12d6571008ff5345fb2
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
                                                'stop': event.begin.date().strftime('%Y-%m-%d'), 
                                                'allday': 'True',
                                                'user_id': responsible_id
                                                })

                external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                                'name': event_xmlid.split('.')[-1], 
                                                'model': 'calendar.event',
<<<<<<< HEAD
                                                'res_id': event_id.id
                                                })

                if event.name[3::] in eves.keys():
                    eve_id = self.env["calendar.event"].create({'name': eves[event.name[3::]],
                                                'start': (event_id.start - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'), 
                                                'stop': (event_id.stop - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
                                                'allday': 'True',
                                                'user_id': responsible_id
                                                })

                    eve_xmlid = f"{IMPORT}.calendar_{eve_id['name'].replace(' ', '_')}_{eve_id['start']}".replace(' ', '_')
                    external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                                'name': eve_xmlid.split('.')[-1], 
                                                'model': 'calendar.event',
                                                'res_id': f"{eve_id.id}"
                                                })
                    
=======
                                                'res_id': event_id.id})     
                                                
                if event.name in eves.keys():
                        eve_id = self.env["calendar.event"].create({'name': eves[event.name],
                                                    'user_id': responsible_id, 
                                                    'start': (event_id.start - datetime.timedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S'), 
                                                    'stop': (event_id.stop - datetime.timedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S')
                                                    })
                
>>>>>>> ff40e74a4ea1dab77dafe12d6571008ff5345fb2
            for resource_calendar in self.env['resource.calendar'].search_read([], ['id', 'hours_per_day']):  
                hours_week = (resource_calendar['hours_per_day'] * 5)
                uid = f"{hours_week}_{event.name.replace(' ', '_')}_{event.begin.date().strftime('%Y-%m-%d')}".replace('.','_')
                leave_xmlid = f"{IMPORT}.leaves_{uid}"
              
                try:
                    ref_try = self.env.ref(leave_xmlid)

                except ValueError: 
                    leave_id = self.env["resource.calendar.leaves"].create({'name': event.name,
                                                    'calendar_id': resource_calendar['id'], 
                                                    'date_from': (event.begin.date()).strftime('%Y-%m-%d %H:%M:%S'), 
                                                    'date_to': (event.begin.date() + datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
                                                    })
                    if event.name in eves.keys():
                        eve_id = self.env["resource.calendar.leaves"].create({'name': eves[event.name],
                                                    'calendar_id': resource_calendar['id'], 
                                                    'date_from': (leave_id.date_from - datetime.timedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S'), 
                                                    'date_to': (leave_id.date_to - datetime.timedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S')
                                                    })

                    external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                                    'name': leave_xmlid.split('.')[-1], 
                                                    'model': 'resource.calendar.leaves',
                                                    'res_id': leave_id.id
                                                    })    

                    if event.name[3::] in eves.keys():
                        leave_eve_id = self.env["resource.calendar.leaves"].create({'name': eves[event.name[3::]],
                                                    'calendar_id': resource_calendar['id'], 
                                                    'date_from': (leave_id.date_from - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'), 
                                                    'date_to': (leave_id.date_to - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
                                                    })
                        
                        uid_eve = f"{hours_week}_{leave_eve_id['name'].replace(' ', '_')}_{leave_eve_id['date_from'].strftime('%Y-%m-%d')}".replace('.','_')
                        leave_eve_xmlid = f"{IMPORT}.leaves_eve_{uid_eve}"

                        external_uid = self.env['ir.model.data'].create({'module': IMPORT, 
                                                    'name': leave_eve_xmlid.split('.')[-1], 
                                                    'model': 'resource.calendar.leaves',
                                                    'res_id': leave_eve_id.id
                                                    })    