odoo.define('one_page_website_calendar.one_page_booking_complete', function (require) {
    'use strict';

    var core = require('web.core');
    var publicWidget = require('web.public.widget');
    var QWeb = core.qweb;

    var ajax = require('web.ajax');
    ajax.loadXML('/one_page_website_calendar/static/src/xml/booking.xml', QWeb);


    publicWidget.registry.OnePageWebsiteCalendarBookingWidget = publicWidget.Widget.extend({
        selector: '#time_slot',
        events: {
            'click #booking_time': '_onSelectBookingTime',
            'click div.next_month': '_onNextMonth',
            'click div.previous_month': '_onPreviousMonth'
        },

        init: function (parent, options) {
            this._super.apply(this, arguments);
            this.month = 0;
        },

        _onSelectBookingTime: async function (event) {
            const booking_type_id = $("#one_page_view_booking_availability input[name='booking_type_id']").val()
            const employee_id = $("#one_page_view_booking_availability input[name='employee_id']").val()
            const date_time = $(event.currentTarget.lastElementChild).val()
            await this._getBookingSlotInfo(booking_type_id, employee_id, date_time)

            // toggle to next tab
            $('#time_slot').hide()
            $('#booking_confirmation').show()
        },

        _getBookingSlotInfo: async function (booking_type_id, employee_id, date_time) {
            await this._rpc({
                route: "/website/calendar/slot/info",
                params: {
                    booking_type: booking_type_id,
                    employee_id: employee_id,
                    date_time: date_time,
                },
            }).then(res => {
                const data = Object.assign({}, res)
                $('#one_page_view_booking_confirmation').replaceWith(QWeb.render('BookingCalendarForm', data));
                $('#booking_header').html('Confirm your details')
            })
        },

        _onNextMonth: async function () {
            this.month += 1
            var employee_id = $("#one_page_view_booking_availability input[name='employee_id']").val()
            var booking_type_id = $("#one_page_view_booking_availability input[name='booking_type_id']").val()
            await this._rpc({
                route: "/website/calendar/booking/slots",
                params: {
                    booking_type: booking_type_id,
                    employee_id: employee_id,
                    month: this.month,
                },
            }).then(res => {
                const slot_details = Object.assign({}, res)
                $('#time_slot').html(
                    QWeb.render('BookingCalendarAvailability', slot_details)
                );
            })
        },

        _onPreviousMonth: async function () {
            var employee_id = $("#one_page_view_booking_availability input[name='employee_id']").val()
            var booking_type_id = $("#one_page_view_booking_availability input[name='booking_type_id']").val()
            if (this.month > 0) {
                this.month -= 1
                await this._rpc({
                    route: "/website/calendar/booking/slots",
                    params: {
                        booking_type: booking_type_id,
                        employee_id: employee_id,
                        month: this.month,
                    },
                }).then(res => {
                    const slot_details = Object.assign({}, res)
                    $('#time_slot').html(
                        QWeb.render('BookingCalendarAvailability', slot_details)
                    );
                })
            } else {
                alert("You cannot make booking for past months")
            }
        }
    })

    return publicWidget.registry.OnePageWebsiteCalendarBookingWidget;
})
