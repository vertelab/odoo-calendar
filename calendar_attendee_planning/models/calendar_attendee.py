# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"

    user_id = fields.Many2one(related="event_id.user_id", store=True)
