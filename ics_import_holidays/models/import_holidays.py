# -*- coding: utf-8 -*-
import datetime
import logging

import requests
from ics import Calendar

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

IMPORT = '__import__'


class ImportHolidays(models.Model):
    _inherit = 'calendar.event'

    @api.model
    def _holiday_cron(self):
        """Mirror the configured .ics holiday calendar into calendar.event
        and resource.calendar.leaves.

        Idempotent: both the events and the leaves are keyed by an
        ir.model.data xmlid derived from the holiday name and date, so a
        monthly re-run only creates what is missing.
        """
        self = self.sudo()
        url = self.env['ir.config_parameter'].sudo().get_param('holiday.url.ics')
        if not url:
            raise UserError(_(
                "No holiday calendar URL is configured. Set it in Settings "
                "(parameter 'holiday.url.ics') before importing holidays."))
        calendar = Calendar(requests.get(url, timeout=30).text)
        responsible = self.env['res.users'].search([('login', '=', 'holidays')], limit=1)
        if not responsible:
            raise UserError(_(
                "The calendar-owning user 'holidays' does not exist. Create it "
                "before importing holidays."))

        for event in list(calendar.timeline):
            event_xmlid = "%s.calendar_%s_%s" % (
                IMPORT,
                event.name.replace(' ', '_'),
                event.begin.date().strftime('%Y-%m-%d'),
            )
            try:
                self.env.ref(event_xmlid)
            except ValueError:
                calendar_event = self.env['calendar.event'].create({
                    'name': event.name,
                    'start': event.begin.date().strftime('%Y-%m-%d'),
                    'stop': event.begin.date().strftime('%Y-%m-%d'),
                    'allday': True,
                    'user_id': responsible.id,
                })
                self.env['ir.model.data'].create({
                    'module': IMPORT,
                    'name': event_xmlid.split('.')[-1],
                    'model': 'calendar.event',
                    'res_id': calendar_event.id,
                })

            # Mirror public holidays into every working schedule as leaves, so
            # the day is not planned as working time.
            for resource_calendar in self.env['resource.calendar'].search_read(
                    [], ['id', 'hours_per_day']):
                hours_week = resource_calendar['hours_per_day'] * 5
                leave_name = '%s_%s_%s' % (
                    hours_week,
                    event.name.replace(' ', '_'),
                    event.begin.date().strftime('%Y-%m-%d'),
                )
                leave_xmlid = '%s.leaves_%s' % (
                    IMPORT, leave_name.replace('.', '_'))
                try:
                    self.env.ref(leave_xmlid)
                except ValueError:
                    leave = self.env['resource.calendar.leaves'].create({
                        'name': event.name,
                        'calendar_id': resource_calendar['id'],
                        'date_from': event.begin.date().strftime('%Y-%m-%d %H:%M:%S'),
                        'date_to': (event.begin.date() + datetime.timedelta(days=1)
                                    ).strftime('%Y-%m-%d %H:%M:%S'),
                    })
                    self.env['ir.model.data'].create({
                        'module': IMPORT,
                        'name': leave_xmlid.split('.')[-1],
                        'model': 'resource.calendar.leaves',
                        'res_id': leave.id,
                    })
