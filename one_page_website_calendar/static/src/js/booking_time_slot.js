odoo.define('one_page_website_calendar.one_page_booking_slot', function (require) {
    'use strict';

    var core = require('web.core');
    var QWeb = core.qweb;
    var publicWidget = require('web.public.widget');

    var ajax = require('web.ajax');
    ajax.loadXML('/one_page_website_calendar/static/src/xml/booking.xml', QWeb);


    publicWidget.registry.OnePageWebsiteCalendarWidget = publicWidget.Widget.extend({
        selector: '#one_page_start_booking',
        events: {
            'click #view_bookings_calendar': '_onCheckAvailability',
        },

        init: function (parent, options) {
            this._super.apply(this, arguments);
        },

        start: function () {

              // params to query the booking slots for the booking type and employee
            //~ var employee_id = $(".o_website_appointment_form select[name='employee_id']").val()
            //~ throw 'Error1';
            //~ var booking_type_id = $(".o_website_appointment_form select[name='booking_type_id']").val()
            //~ throw 'Error2';
            //~ this._getBookingSlots(booking_type_id, employee_id)
            //~ throw 'Error2';

            // toggle to next tab
            //~ $('#start_booking').hide()
            //~ $('#time_slot').show()
            var defs = [];
            defs.push(this._super.apply(this, arguments));
            return Promise.all(defs);
            
        },

        _onCheckAvailability:  function (e) {
            // params to query the booking slots for the booking type and employee
            var employee_id = $(".o_website_appointment_form select[name='employee_id']").val()
            //~ throw 'Error1';
            var booking_type_id = $(".o_website_appointment_form select[name='booking_type_id']").val()
            //~ throw 'Error2';
            this._getBookingSlots(booking_type_id, employee_id)
            //~ throw 'Error2';

            // toggle to next tab
            $('#start_booking').hide()
            $('#time_slot').show()

        },

        _getBookingSlots: function (booking_type_id, employee_id) {
            var self = this
            this._rpc({
                route: "/website/calendar/booking/slots",
                params: {
                    booking_type: booking_type_id,
                    employee_id: employee_id,
                },
            }).then(res => {
                const data = Object.assign({}, res)
                $('#one_page_view_booking_availability').replaceWith(QWeb.render('BookingCalendarAvailability', data));
                $('#booking_header').html('Booking Time')
            })
        },
    })

    return publicWidget.registry.OnePageWebsiteCalendarWidget
})
