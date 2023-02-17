odoo.define('website_appointment.booking_actions', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    const wUtils = require('website.utils');

    publicWidget.registry.WebsiteAppointment = publicWidget.Widget.extend({
        selector: '.o_website_calendar',
        events: {
            'click #previous_month': '_view_previous_month',
            'click #next_month': '_view_next_month',
            'click #employee_selector': '_view_employee_slot',
        },

        init: function () {
            this._super.apply(this, arguments);
            this.month = 0;
            this.employee_id;
        },

        start: function (parent) {
            if ($("input[name='employee_id']").length === 1) {
                this.employee_id = parseInt($("input[name='employee_id']").val())
            }
            return this._super.apply(this, arguments);
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------
        _view_employee_slot: async function (event) {
            var booking_type_id = $("input[name='booking_type_id']").val()

            this.employee_id = $(event.target).find("input[name='employee_id']").val()

            $(event.target).toggleClass('.selected');

            await this._rpc({
                route: "/slots",
                params: {
                    booking_type: booking_type_id,
                    month: this.month,
                    employee_id: this.employee_id
                },
            }).then(res => {
                $("#booking_calendar").replaceWith(res)
            })
        },

        _view_next_month: async function () {
            var booking_type_id = $("input[name='booking_type_id']").val()
            var self = this;

            if (booking_type_id) {
                await this._rpc({
                    route: "/slots",
                    params: {
                        booking_type: booking_type_id,
                        month: this.month + 1,
                        employee_id: this.employee_id
                    },
                }).then(res => {
                    if (res == false) {
                        alert("No more booking time")
                    } else {
                        this.month += 1
                        $("#booking_calendar").replaceWith(res)
                    }
                })
            }
        },

        _view_previous_month: async function () {
            var booking_type_id = $("input[name='booking_type_id']").val()

            if (this.month > 0) {
                this.month -= 1
                await this._rpc({
                    route: "/slots",
                    params: {
                        booking_type: booking_type_id,
                        month: this.month,
                        employee_id: this.employee_id
                    },
                }).then(res => {
                    $("#booking_calendar").replaceWith(res)
                })
            } else {
                alert("You cannot make booking for past months")
            }
        },
    });
});

