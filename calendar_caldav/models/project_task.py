# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Give ``project.task`` a stable CalDAV UID.

A VTODO is stored as a task with no project, which is what Odoo's own
Att-göra view uses. The UID has to survive a rename and a move between
projects, so it is generated once and never derived from the id.
"""

from uuid import uuid4

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    dav_href = fields.Char(

        string="DAV href",

        index=True,

        readonly=True,

        help="File name (href stem) the client last used for this record.",

    )


    caldav_uuid = fields.Char(
        string='CalDAV UID',
        copy=False,
        index=True,
        help='Stable identifier used as the VTODO UID. Generated on first '
             'use; never changes, so a client keeps seeing the same task '
             'after a rename.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('caldav_uuid'):
                vals['caldav_uuid'] = str(uuid4())
        return super().create(vals_list)
