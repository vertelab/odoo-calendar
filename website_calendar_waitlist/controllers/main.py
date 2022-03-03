import datetime
import logging

from odoo import http, _, fields
from odoo.http import request

from odoo.addons.website_calendar_ce.controllers.main import WebsiteCalendar


_logger = logging.getLogger(__name__)


class ExtendedWebsiteCalendar(WebsiteCalendar):

    def _has_available_slots(self, Slots):
        for data in Slots:
            for week in data.get("weeks", []):
                for day in week:
                    if day.get("slots", []):
                        return True
        return False


    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/booking'], type='http', auth="public", website=True)
    def calendar_booking(self, booking_type=None, employee_id=None, timezone=None, failed=False, **kwargs):
        request.session['timezone'] = timezone or booking_type.booking_tz
        Employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None
        Slots = booking_type.sudo()._get_booking_slots(request.session['timezone'], Employee)

        _logger.warning(f"{booking_type=}")
        if request.env.user.partner_id == request.env.ref('base.public_partner'):
            # TODO: dont allow public user!

            return request.render("website_calendar_waitlist.booking_error", {
                })
        elif self._has_available_slots(Slots):
            return super().calendar_booking(booking_type, employee_id, timezone, failed, **kwargs)
        else:
            return request.render("website_calendar_waitlist.booking_form", {
                    "employee": Employee,
                    "booking_type": booking_type,
                    "timezone": request.session["timezone"],
                    "failed": failed,
                    "partner_data": request.env.user.partner_id,
                })

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/waitlist'], type="http", auth="public", website=True)
    def waitlist(self, booking_type=None, employee_id=None, **kwargs):
        _logger.warning("got waitlist!")
        already_in_queue = False
        # Create waitlist
        partner_id = request.env.user.partner_id
        user_id = request.env['res.users'].sudo().search([('partner_id', '=', partner_id.id)])

        waitlist_data = {
                'related_user_id': user_id.id,
                'related_booking_type_id': booking_type.id,
                }
        if employee_id:
            waitlist_data['employee_id'] = int(employee_id)

        domain = [(key, '=', value) for key, value in waitlist_data.items()]


        _logger.warning(f"{domain=}")
        if queue_position := request.env['calendar.booking.type.waitlist'].sudo().search(domain):
            already_in_queue = True
        else:
            _logger.warning(f"{queue_position=}")
            queue_position = request.env['calendar.booking.type.waitlist'].sudo().create(waitlist_data)
        data = {
                "already_in_queue": already_in_queue,
                "queue_position": queue_position,
        }
        return request.render("website_calendar_waitlist.waitlist_confirmation", data)

