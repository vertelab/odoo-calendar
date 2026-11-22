import datetime
import logging

from odoo import http, _, fields
from odoo.http import request

from odoo.addons.website_calendar_ce.controllers.main import WebsiteCalendar


_logger = logging.getLogger(__name__)


class ExtendedWebsiteCalendar(WebsiteCalendar):
    def _create_event(self, request, Employee, data):
        event = super(ExtendedWebsiteCalendar, self)._create_event(request, Employee, data)
        self._add_task_to_project(event, Employee, data)
        return event

    def _add_task_to_project(self, event, Employee, data):
        booking_type = request.env['calendar.booking.type'].sudo().browse(data['booking_type_id'])
        project = request.env['project.project'].sudo().browse(booking_type.related_project_id.id)
        related_users = [x for x in data.get('partner_ids', []) if x[1] != Employee.user_partner_id.id]
        customer_id = None
        if related_users:
            customer_id = related_users[0][1]

        data = {
                'name': event.name,
                'project_id': booking_type.related_project_id.id,
                'user_id': Employee.user_id.id,
                'recurring_task': False,
                'description': data.get('description').replace("\n", "<br/>"),
                'partner_id': customer_id,
                'access_token': event.access_token,
                'start': event.start,
                'stop': event.stop,
                }

        request.env['project.task'].sudo().create(data)

