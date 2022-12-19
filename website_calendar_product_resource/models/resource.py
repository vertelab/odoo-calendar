# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResourceResource(models.Model):
    _inherit = "resource.resource"

    product_id = fields.Many2one("product.product", copy=False)
