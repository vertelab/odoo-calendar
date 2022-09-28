from odoo import models, api, fields, _


class CalendarBooking(models.Model):
    _inherit = "calendar.booking.type"

    product_ids = fields.Many2many("product.product", string="Products")