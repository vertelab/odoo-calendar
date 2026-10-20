# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class CalendarEventModify(models.Model):
    _inherit = "calendar.event"

    resource_ids = fields.Many2many(
        comodel_name='resource.resource',
        string='Resource',
        domain=[('resource_type', '=', 'material')],
        help="Material resources booked for this event.",
    )
    resource_status = fields.Char(
        string='Resource status',
        readonly=True,
        compute='_compute_resource_status',
        help="Shows a warning when a booked resource is already taken "
             "by another event during the same period.",
    )

    @api.depends('resource_ids', 'start', 'stop')
    def _compute_resource_status(self):
        """Flag double bookings of material resources.

        Two events overlap when one starts before the other ends and ends
        after the other starts. The previous implementation inverted this
        test and searched with a domain that could never match, so a
        conflict was never reported.
        """
        for event in self:
            event.resource_status = False
            if not event.resource_ids or not event.start or not event.stop:
                continue

            # Overlap: existing.start < event.stop AND existing.stop > event.start
            conflicts = self.env['calendar.event'].search([
                ('id', '!=', event.id),
                ('start', '<', event.stop),
                ('stop', '>', event.start),
            ])
            if not conflicts:
                continue

            taken = conflicts.filtered(
                lambda c: c.resource_ids & event.resource_ids
            )
            if not taken:
                continue

            messages = []
            for resource in event.resource_ids:
                for conflict in taken:
                    if resource not in conflict.resource_ids:
                        continue
                    if conflict.create_date < event.create_date:
                        messages.append(
                            _("%(resource)s is already booked by %(event)s",
                              resource=resource.name, event=conflict.name)
                        )
                    else:
                        messages.append(
                            _("%(event)s tries to book %(resource)s",
                              event=conflict.name, resource=resource.name)
                        )
            if messages:
                event.resource_status = "; ".join(messages)
