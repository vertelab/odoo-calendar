# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Scheduling lives in data/cron_tasks.xml (cron.task), not here. Creating an
# ir.cron when the settings form is saved cannot be verified against the code
# and duplicates on every save; a cron.task carries model_name/method_name as
# fields, so a missing method fails once with a descriptive error.


class ResCalendarSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ics_url = fields.Char(
        string='URL of the ICS file',
        config_parameter='holiday.url.ics',
        help="Holiday calendar to import. The events are mirrored into the "
             "calendar and into every working schedule as leaves.",
    )
