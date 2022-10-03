from odoo import models, api, fields, _


class CalendarBooking(models.Model):
    _inherit = "calendar.booking.type"

    product_ids = fields.Many2many("product.product", "calendar_booking_type_product_rel", string="Products")


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    product_id = fields.Many2one("product.product", string="Product")
