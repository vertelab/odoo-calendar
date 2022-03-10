import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class Meeting(models.Model):
    _inherit = "calendar.event"

    # ~ def unlink(self, *args, **kwargs):
        # ~ _logger.warning(f"{self.booking_type_id=}")
        # ~ if self.booking_type_id:
            # ~ related_task = self.env['project.task'].sudo().search([('access_token', '=', self.access_token)])
            # ~ if len(related_task) != 1:

                # ~ #TODO: Better error

                # ~ raise AssertionError("Too many/few related tasks for access token %s", self.access_token)
            # ~ related_task.kanban_state = "blocked"
            # ~ related_task.message_post(body=_("Event canceled by user"))
        # ~ return super().unlink(*args, **kwargs)
