# -*- coding: utf-8 -*-
import datetime
import logging

import requests
from icalendar import Calendar

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
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_(
                "Could not read the holiday calendar at %(url)s: %(error)s",
                url=url, error=exc)) from exc
        # webcal.guru's file makes python-ics 0.7.3 recurse until the stack
        # blows, so the calendar is read with icalendar instead.
        calendar = Calendar.from_ical(response.content)

        # The 'holidays' user is module data (data/users.xml), so it exists as
        # soon as the module is installed and this cron does not depend on
        # somebody having saved the settings form first.
        responsible = self.env.ref('ics_import_holidays.user_holidays')

        for component in calendar.walk('VEVENT'):
            name = str(component.get('SUMMARY') or '').strip()
            begin = component.get('DTSTART').dt
            if isinstance(begin, datetime.datetime):
                begin = begin.date()
            if not name:
                continue
            event_xmlid = "%s.calendar_%s_%s" % (
                IMPORT,
                name.replace(' ', '_'),
                begin.strftime('%Y-%m-%d'),
            )
            if not self.env.ref(event_xmlid, raise_if_not_found=False):
                calendar_event = self.env['calendar.event'].create({
                    'name': name,
                    'start': begin.strftime('%Y-%m-%d'),
                    'stop': begin.strftime('%Y-%m-%d'),
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
                # Key the leave on the calendar id, not on hours_per_day:
                # two schedules can share the same hours, and keying on the
                # hours would make them collide on one xmlid so the second
                # schedule silently never got its leave.
                leave_name = 'cal%s_%s_%s' % (
                    resource_calendar['id'],
                    name.replace(' ', '_'),
                    begin.strftime('%Y-%m-%d'),
                )
                leave_xmlid = '%s.leaves_%s' % (
                    IMPORT, leave_name.replace('.', '_'))
                if not self.env.ref(leave_xmlid, raise_if_not_found=False):
                    leave = self.env['resource.calendar.leaves'].create({
                        'name': name,
                        'calendar_id': resource_calendar['id'],
                        'date_from': begin.strftime('%Y-%m-%d %H:%M:%S'),
                        'date_to': (begin + datetime.timedelta(days=1)
                                    ).strftime('%Y-%m-%d %H:%M:%S'),
                    })
                    self.env['ir.model.data'].create({
                        'module': IMPORT,
                        'name': leave_xmlid.split('.')[-1],
                        'model': 'resource.calendar.leaves',
                        'res_id': leave.id,
                    })
