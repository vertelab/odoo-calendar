# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"
    _rec_name = 'event_id'

    def _compute_week_number(self):
        # self.event_week = datetime.date(self.event_date_start).isocalendar()[1]
        _logger.warning(datetime.date(self.event_date_start).isocalendar()[1])
        _logger.warning(self.event_date_start)

    user_id = fields.Many2one(related='event_id.user_id', store=True)
    event_date_start = fields.Datetime(related='event_id.start', store=True)
    event_date_end = fields.Datetime(related='event_id.stop')
    event_week = fields.Integer(compute='_compute_week_number', store=True)
