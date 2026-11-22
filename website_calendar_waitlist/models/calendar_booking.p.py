import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class Waitlist(models.Model):
    _name = "calendar.booking.type.waitlist"
    _description = "Waitlist for calendar types"

    related_user_id = fields.Many2one(
            "res.users",
            string="User",
            required=True,
            )

    related_booking_type_id = fields.Many2one(
            "calendar.booking.type",
            required=True,
            )

    current_position = fields.Integer(
            compute="_compute_position",
            store=True,
            default=-10,
            )

    employee_id = fields.Many2one(
            "hr.employee",
            string="Employee",
            )

    @api.depends("related_booking_type_id", "related_booking_type_id.related_wait_list_ids")
    def _compute_position(self):
        for record in self:
            for i, row in enumerate(record.related_booking_type_id.related_wait_list_ids, 1):
                if row.id == record.id:
                    record.current_position = i
                    break
            else:
                record.current_position = -10

class CalendarBookingType(models.Model):
    _inherit = "calendar.booking.type"

    related_wait_list_ids = fields.One2many(
            "calendar.booking.type.waitlist",
            "related_booking_type_id",
            string="Waitlist",
            )
