# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_booking = fields.Boolean(string="Can be Booked")
    allow_booking_range = fields.Boolean(string="Allow Booking Range")

    def _get_bookings(self):
        for rec in self:
            event_ids = self.env['calendar.event'].search([('product_id.id', '=', rec.product_variant_id.id)])
            if event_ids:
                rec.calendar_event_id = event_ids.ids
            else:
                rec.calendar_event_id = False

    calendar_event_id = fields.Many2many(
        'calendar.event', 'calendar_event_product_rel', readonly=True, compute=_get_bookings)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_bookings(self):
        for rec in self:
            event_ids = self.env['calendar.event'].search([('product_id.id', '=', rec.id)])
            if event_ids:
                rec.calendar_event_id = event_ids.ids
            else:
                rec.calendar_event_id = False

    calendar_event_id = fields.Many2many(
        'calendar.event', 'calendar_event_product_rel', readonly=True, compute=_get_bookings)

    def calendar_verify_product_availability(self, partner, date_start, date_end):
        """ verify availability of the partner(s) between 2 datetime on their calendar
        """
        if bool(self.env['calendar.event'].search_count([
            ('partner_ids', 'in', partner.ids),
            ('product_id', 'in', self.ids),
            '|', '&', ('start', '<', fields.Datetime.to_string(date_end)),
            ('stop', '>', fields.Datetime.to_string(date_start)),
            '&', ('allday', '=', True),
            '|', ('start_date', '=', fields.Date.to_string(date_end)),
            ('start_date', '=', fields.Date.to_string(date_start))])):
            return False
        return True
