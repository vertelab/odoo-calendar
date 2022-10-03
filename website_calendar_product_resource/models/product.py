# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

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
