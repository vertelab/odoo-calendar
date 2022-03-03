odoo.define('one_page_website_calendar.one_page_booking_complete', function (require) {
    'use strict';

    var core = require('web.core');
    var options = require('web_editor.snippets.options');
    var publicWidget = require('web.public.widget');
    var rpc = require('web.rpc');
    var QWeb = core.qweb;

    var ajax = require('web.ajax');

    ajax.loadXML('/one_page_website_calendar/static/src/xml/booking.xml', QWeb);


    publicWidget.registry.OnePageWebsiteCalendarBookingWidget = publicWidget.Widget.extend({
        xmlDependencies: [
            "/one_page_website_calendar/static/src/xml/booking.xml",
        ],
        selector: '#booking_confirmation, #time_slot, #one_page_view_booking_availability, #one_page_start_booking, #booking_confirmation',
        events: {
            'click #booking_time': '_onSelectBookingTime',
            'click .o_calendar_days': '_onSelectBookingTime',

        },

        // _onSelectBookingTime: function () {
        //     console.log("time time")
        // },
    })

    return publicWidget.registry.OnePageWebsiteCalendarBookingWidget;
})
