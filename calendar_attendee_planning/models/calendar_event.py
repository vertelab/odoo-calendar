# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarEventModify(models.Model):
    _inherit = "calendar.event"

    def create(self, vals_list):
        res = super().create(vals_list)
        #_logger.warning(f"BAPIDI {self} {vals_list} {res}")
        # for vals in vals_list:
            # res = super().create(vals)
            # _logger.warning(f"BAPIDI {self} {vals} {res}")
            # if res.recurrence_id != False and res.contract_id == False:
            #     res.contract_id = res.recurrence_id.base_event_id.contract_id.id
                
            # _logger.warning(f"calendar event {self.env['calendar.event'].search_read([('id', '=', res.id)],[])}")

        return res
        
    #consider what to do about returning res in the middle of loop
    def write(self, vals):
        res = super().write(vals)
        #_logger.warning(f"BOPIDI {res} {vals} {res}")

        # for cal in self:
        #     res = super().write(cal)
        #     _logger.warning(f"BOPIDI {cal} {vals} {res}")
            # if cal.recurrence_id != False and cal.contract_id == False:
            #     cal.contract_id = cal.recurrence_id.base_event_id.contract_id.id
        
        return res  

# class CalendarRecurrenceModify(models.Model):
#     _inherit = "calendar.recurrence"
        
#     #consider what to do about returning res in the middle of loop
#     def write(self, vals):
#         res = super(CalendarRecurrenceModify, self).write(vals)
#         for rec in self:
#             _logger.warning(f"first loop {rec}")
#             for event in rec.calendar_event_ids:
#                 _logger.warning(f"second loop {event}")
#                 event.write({'contract_id': rec.base_event_id.contract_id})
#                 self.env['calendar.event'].browse(rec.base_event_id)

#         return res  

