import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class Project(models.Model):
    _inherit = "project.project"

    related_online_booking_ids = fields.One2many(
            "calendar.booking.type",
            "related_project_id",
            string="Related online_booking_ids",
            )


class Task(models.Model):
    _inherit = "project.task"

    access_token = fields.Char(
            string='Access token',
            readonly=True,
            )

    start = fields.Date(
            string="Start",
            )

    stop = fields.Date(
            string="Stop",
            )
