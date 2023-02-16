# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarEventModify(models.Model):
    _inherit = "calendar.event"

    resource_ids = fields.Many2many(comodel_name='resource.resource',string='Resource',domain="[('resource_type','=','material')]") # relation|column1|column2
    resource_status = fields.Char(readonly=True)
    resource_status = fields.Char(readonly=True,compute='onchange_resource')
    

    @api.depends("resource_ids")
    def onchange_resource(self):
        
        def overlap(self, other):
            if other.start < self.start < other.stop:
                return False
            elif other.start < self.stop < other.stop:
                return False
            elif self.start < other.start < self.stop:
                return False
            elif self.start < other.stop < self.stop:
                return False
            return True

        calendars = self.env['calendar.event'].search(
            [
                ('stop_date','<=',self.start_date),
                ('start_date','>=',self.start_date),
               
                ]
            )
        _logger.warning(calendars)
        self.resource_status=''
        for c in calendars:
            if overlap(self,c):
                for r in self.resource_ids:
                    if c.create_date < self.create_date:
                        self.resource_status = _('%s are already booked by %s') % (r.name,c.name)
                    else:
                        self.resource_status = _('%s tries to book %s') % (c.name,r.name)
        
