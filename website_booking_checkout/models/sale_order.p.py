import logging
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, models, fields, _
from odoo.http import request
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    booking_type_id = fields.Many2one("calendar.booking.type", string="Booking Type")
    sale_order_booking_id = fields.Many2one("sale.order.booking", string="SO Booking", index=True, copy=False)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # booking_type_id = fields.Many2one("calendar.booking.type", string="Booking Type")
    sale_order_booking_id = fields.One2many("sale.order.booking", 'sale_order_id', string="SO Booking", copy=False,
                                            readonly=True)
    # start_date = fields.Datetime(string="Start Date")
    # end_date = fields.Datetime(string="End Date")

    def _create_booking(self, booking_vals):
        sale_order_line_id = self.env['sale.order.line'].browse(booking_vals.get('sale_order_line_id'))
        if sale_order_line_id:
            so_booking_id = self.env['sale.order.booking'].search([
                ('sale_order_id', '=', booking_vals.get('sale_order_id')),
                ('sale_order_line_id', '=', booking_vals.get('sale_order_line_id'))
            ])
            if not so_booking_id:
                so_booking_id = self.env['sale.order.booking'].create(booking_vals)
            else:
                so_booking_id.write(booking_vals)
            sale_order_line_id.write({'sale_order_booking_id': so_booking_id.id})


class OrderBooking(models.Model):
    _name = 'sale.order.booking'
    _description = 'Sale Order Booking'
    _rec_name = 'sale_order_line_id'

    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    sale_order_line_id = fields.Many2one('sale.order.line', string="SO Line", ondelete="cascade",
                                         index=True, copy=False)
    booking_type_id = fields.Many2one("calendar.booking.type", string="Booking Type")

    def unlink(self):
        if self.sale_order_line_id._check_line_unlink():
            raise UserError(_('You can not remove an order booking line once the sales order is confirmed.\nYou '
                              'should rather set the quantity to 0.'))
        return super(OrderBooking, self).unlink()
