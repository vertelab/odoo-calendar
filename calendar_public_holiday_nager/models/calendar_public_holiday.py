# Copyright 2025 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError,UserError
from datetime import datetime
import logging
import requests

_logger = logging.getLogger(__name__)

class ResourceCalendarPublicHoliday(models.Model):
    _inherit = "calendar.public.holiday"

    def fetch_public_holidays(self):
        for cal in self:
            url = f"https://date.nager.at/api/v3/PublicHolidays/{cal.year}/{cal.country_id.code}"
            response = requests.get(url)
            if response.status_code == 200:
                cal.line_ids.unlink()
                for day in response.json():
                    _logger.warning(f"{day=}")
                    holidays = cal.line_ids.filtered(lambda d: d.date == datetime.strptime(day['date'], "%Y-%m-%d").date())
                    _logger.warning(f"{day=} {holidays=}")
                    if len(holidays) > 0: # Only one holyday at the same date
                        holidays[0].name += f", {day['localName']}"
                    else:
                        cal.line_ids.create({'name': day['localName'],'date':day['date'],'public_holiday_id':cal.id})
# TODO lägga på name  och localName via översättning
                        # ~ self.env['ir.translation'].create({
                            # ~ 'name': f"{holiday._name},name",
                            # ~ 'res_id': holiday.id,
                            # ~ 'lang': 'sv_SE',  # Byt till önskat språk
                            # ~ 'type': 'model',
                            # ~ 'value': day['translatedName'],
                            # ~ 'state': 'translated',
                        # ~ })

            else:
                raise UserError(f"Could not fetch holidays {response.status_code} - {response.reason}{response.text}\n{url}")

    def fetch_public_holidays_next(self):
        self.ensure_one()
        cal = self.env['calendar.public.holiday'].create({'year':self.year + 1,'country_id':self.country_id.id,})
        cal.fetch_public_holidays()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Public Holiday',
            'res_model': 'calendar.public.holiday',
            'view_mode': 'form',
            'view_id': self.env.ref('calendar_public_holiday.view_calendar_public_holiday_form').id,
            'res_id': cal.id,  
            'target': 'current',
        }
