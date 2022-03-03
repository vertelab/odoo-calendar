odoo.define('one_page_website_calendar.one_page_booking_complete', function (require) {
    'use strict';

    var core = require('web.core');
    var publicWidget = require('web.public.widget');
    var rpc = require('web.rpc');
    var QWeb = core.qweb;

    var ajax = require('web.ajax');
    ajax.loadXML('/one_page_website_calendar/static/src/xml/booking.xml', QWeb);


    publicWidget.registry.OnePageWebsiteCalendarBookingWidget = publicWidget.Widget.extend({
        selector: '#time_slot',
        events: {
            'click #booking_time': '_onSelectBookingTime',
        },

        _onSelectBookingTime: async function (event) {
            const booking_type_id = $("#one_page_view_booking_availability input[name='booking_type_id']").val()
            const employee_id = $("#one_page_view_booking_availability input[name='employee_id']").val()
            const date_time = $(event.currentTarget.lastElementChild).val()
            // console.log(date_time)
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
    })

    return publicWidget.registry.OnePageWebsiteCalendarBookingWidget;
})
