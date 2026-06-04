from uuid import uuid4, UUID
from odoo import models, fields, api


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    uuid = fields.Char(
        string="UUID",
        readonly=True,
        default=lambda self: str(uuid4()),
        index=True,
    )
    dav_last_modified = fields.Datetime(
        string="Last Modified (DAV)",
        compute="_compute_dav_last_modified",
        store=True,
        index=True,
    )

    @api.depends("write_date")
    def _compute_dav_last_modified(self):
        for event in self:
            event.dav_last_modified = event.write_date

    def _get_or_create_uuid(self):
        if self.uuid:
            return self.uuid
        return str(UUID(int=self.id))

    def init(self):
        self.env.cr.execute(
            "UPDATE calendar_event SET uuid = gen_random_uuid()::text WHERE uuid IS NULL"
        )
