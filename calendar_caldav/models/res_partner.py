# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Stable DAV UIDs for contacts.

``calendar.event`` already has a ``uuid`` column (Odoo core). ``res.partner``
does not, so a CardDAV client's UID was falling back to the database id —
which works, but breaks the moment a contact is merged, and it is not the
UID the client stored. A contact that moves between two addressbooks
(``contacts`` and ``personal-contacts``) would otherwise look like a
different person in each.

The field is a plain computed-with-inverse char: generated once, then
stable. ``copy=False`` so duplicating a partner does not duplicate its UID.
"""
import uuid as uuid_lib

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    dav_href = fields.Char(

        string="DAV href",

        index=True,

        readonly=True,

        help="File name (href stem) the client last used for this record.",

    )


    caldav_uuid = fields.Char(
        string='DAV UID',
        copy=False,
        index=True,
        help='Stable identifier used as the CardDAV UID. Generated on first '
             'use; never changes, so a client keeps seeing the same contact '
             'after a rename or a merge.',
    )

    def _ensure_caldav_uuid(self):
        """Give every partner in ``self`` a UID if it has none.

        Called from the CardDAV layer before a record is serialised, so a
        contact that predates this field still gets a stable UID instead of
        falling back to its database id.
        """
        missing = self.filtered(lambda partner: not partner.caldav_uuid)
        for partner in missing:
            partner.caldav_uuid = str(uuid_lib.uuid4())
        return missing

    @api.model_create_multi
    def create(self, vals_list):
        # A contact created from a client PUT arrives with a UID already;
        # one created in the Odoo UI gets one here so CardDAV never has to
        # fall back to the database id.
        for vals in vals_list:
            if not vals.get('caldav_uuid'):
                vals['caldav_uuid'] = str(uuid_lib.uuid4())
        return super().create(vals_list)


class ResPpartner(models.Model):
    """Personal contacts (personal_contact_carddav).

    res.ppartner does not inherit res.partner — it is a standalone model
    with its own address fields — so the DAV UID has to be declared here
    too, not inherited.
    """
    _inherit = 'res.ppartner'

    caldav_uuid = fields.Char(
        string='DAV UID',
        copy=False,
        index=True,
        help='Stable identifier used as the CardDAV UID.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('caldav_uuid'):
                vals['caldav_uuid'] = str(uuid_lib.uuid4())
        return super().create(vals_list)
