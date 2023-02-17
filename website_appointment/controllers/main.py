from odoo import exceptions, http, fields, _
from odoo.http import request, route


class AppointmentController(http.Controller):

    @http.route([
        '/appointment/',
        '/appointment/<model("calendar.booking.type"):booking_type>/'], type='http', auth="public", website=True)
    def appointment_type_index(self, booking_type=None, **kwargs):
        if not booking_type:
            country_code = request.session.geoip and request.session.geoip.get('country_code')
            if country_code:
                suggested_booking_types = request.env['calendar.booking.type'].search([
                    '|', ('country_ids', '=', False),
                    ('country_ids.code', 'in', [country_code])])
            else:
                suggested_booking_types = request.env['calendar.booking.type'].search([])
            if not suggested_booking_types:
                return request.render("website_appointment.setup", {})
            booking_type = suggested_booking_types[0]
        else:
            suggested_booking_types = booking_type

        return request.render("website_appointment.index", {
            'booking_type': booking_type,
            'suggested_booking_types': suggested_booking_types,
        })

    @http.route(['/appointment/<model("calendar.booking.type"):booking_type>/booking'], type='http', auth="public",
                website=True)
    def appointment_booking(self, booking_type=None, month=0, timezone=None, failed=False, title=None, description=None,
                            **kwargs):
        # booking_type._assignation_method()
        appointment_employee_ids = booking_type._assignation_method()
        # appointment_employee_ids = booking_type.sudo().mapped('employee_ids')
        if not timezone:
            timezone = booking_type.booking_tz

        slot_ids = booking_type.sudo()._paginated_appointment_slots(
            booking_type, timezone, appointment_employee_ids, int(month)
        )

        return request.render("website_appointment.booking", {
            'booking_type': booking_type,
            'employee_ids': appointment_employee_ids,
            'timezone': timezone,
            'failed': failed,
            'slots': slot_ids,
            'description': description if description else _(
                "Fill your personal information in the form below, and confirm the booking. We'll send an invite to "
                "your email address"),
            'title': title if title else _("Book meeting"),
        })

    @http.route(['/slots'], type='json', auth="public", website=True)
    def toggle_appointment_slots(self, booking_type=None, employee_id=None, month=0, description=None, title=None,
                                 **kwargs):
        booking_type = request.env['calendar.booking.type'].sudo().browse(int(booking_type)) if booking_type else None
        timezone = booking_type.booking_tz

        print(booking_type)

        if employee_id:
            appointment_employee_ids = request.env['hr.employee'].sudo().browse(int(employee_id))
        else:
            appointment_employee_ids = booking_type._assignation_method()

        slot_ids = booking_type.sudo()._paginated_appointment_slots(
            booking_type, timezone, appointment_employee_ids, int(month)
        )

        if slot_ids:
            return request.env['ir.ui.view']._render_template("website_calendar_ce.booking_calendar", {
                'booking_type': booking_type,
                # 'employee_id': hr_employee_id,
                'timezone': request.session['timezone'],
                'slots': slot_ids,
                'description': description if description else _(
                    "Fill your personal information in the form below, and confirm the booking. We'll send an invite "
                    "to your email address"),
                'title': title if title else _("Book meeting"),
            })
        else:
            return False
