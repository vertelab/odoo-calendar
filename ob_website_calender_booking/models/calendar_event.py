# -*- coding: utf-8 -*-

from odoo import fields, models
class CalendarEventEmail(models.Model):

    _inherit = "calendar.event"
    
    booking_email = fields.Char(string="Email")