import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class CalendarBookingType(models.Model):
    _inherit = "calendar.booking.type"

    related_project_id = fields.Many2one(
            "project.project",
            string="Related project",
            )

