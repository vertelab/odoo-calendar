# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"
    _rec_name = 'event_id'

    user_id = fields.Many2one(related='event_id.user_id', store=True, group_expand='_read_attendee_ids')
    event_date_start = fields.Datetime(related='event_id.start', store=True)
    event_date_end = fields.Datetime(related='event_id.stop')
    event_week = fields.Char(compute='_compute_week_number', store=True)

    @api.depends('event_date_start')
    def _compute_week_number(self):
        for rec in self:
            # _logger.warning(f"FIRST: {date.today().year} SECOND: {datetime.date(rec.event_date_start).isocalendar()[1]} THIRD: {datetime.strptime('%s-%s-%s' % (date.today().year, datetime.date(rec.event_date_start).isocalendar()[1], 1), '%G-%V-%u')} FOURTH: {datetime.strptime('%s-%s-%s' % (date.today().year, datetime.date(rec.event_date_start).isocalendar()[1], 1), '%G-%V-%u').strftime('%Y-%m-%d')}")
            rec.event_week = datetime.strptime('%s-%s-%s' % (date.today().year, datetime.date(rec.event_date_start).isocalendar()[1], 1), '%G-%V-%u').strftime('%Y-%m-%d')
            # rec.event_week = datetime.date(rec.event_date_start).isocalendar()[1]

    def _read_attendee_ids(self, custom, domain, order):
        employees = self.env['res.users'].search([])
        return employees
        