# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Personal contacts.

Moved here from ``personal_contact_carddav`` (2026-11-17). That module sat on
top of the Radicale track (``contact_carddav`` -> ``calendar_dav`` ->
``base_dav``), which is retired; keeping the model there kept the whole chain
alive in every client install.

``res.ppartner`` does not inherit ``res.partner`` - it is a standalone model
with its own address fields, so it carries no company or commercial-entity
semantics. That is deliberate: a personal contact is one user's own address
book entry, not a business relationship.

The DAV UID lives in ``res_partner.py`` (``_inherit = 'res.ppartner'``), not
here, to keep the CardDAV concern separate from the model definition.
"""
from odoo import fields, models


class ResPpartner(models.Model):
    _name = 'res.ppartner'
    _description = 'Personal Partner'
    _order = 'name'
    _rec_name = 'name'
    _check_company_auto = False

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        index=True,
        default=lambda self: self.env.user,
    )
    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    company_name = fields.Char(string='Company')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    zip = fields.Char(string='ZIP')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    notes = fields.Text(string='Notes')
    image = fields.Binary(string='Image', attachment=True)
    category_ids = fields.Many2many(
        'res.partner.category',
        'res_ppartner_category_rel',
        'ppartner_id',
        'category_id',
        string='Tags',
    )
