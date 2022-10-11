from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    booking_type_id = fields.Many2one("calendar.booking.type", string="Booking Type")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    booking_type_id = fields.Many2one("calendar.booking.type", string="Booking Type")
    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")
