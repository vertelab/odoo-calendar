odoo.define('website_booking_checkout.booking_actions', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    const wUtils = require('website.utils');

    publicWidget.registry.WebsiteBookingCheckout = publicWidget.Widget.extend({
        selector: '.o_website_product_booking',
        events: {
            'click #product_previous_month': '_onPreviousBookingMonth',
            'click #product_next_month': '_onNextBookingMonth',
            'click td.dropdown > div.dropdown-menu > a': '_HighlightMultipleBookingSlots',
            'click #proceed_with_booking': '_BookProduct'
        },

        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
            this.product_month = 0;
            this.x_click = 0;
            this.starting_slot;
            this.ending_slot;
        },
        /**
         * @override
         * @param {Object} parent
         */
        start: function (parent) {
            return this._super.apply(this, arguments);
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------
        _onNextBookingMonth: async function () {
            var product_id = $("input[name='product_id']").val()
            var booking_type_id = $("input[name='booking_type_id']").val()
            var self = this;

            if (product_id && booking_type_id) {
                await this._rpc({
                    route: "/product-booking-slots",
                    params: {
                        booking_type: booking_type_id,
                        product_id: product_id,
                        month: this.product_month + 1,
                    },
                }).then(res => {
                    if (res == false) {
                        alert("No more booking time")
                    } else {
                        this.product_month += 1
                        $("#product_booking_calendar").replaceWith(res)
                    }
                })
            }
        },

        _onPreviousBookingMonth: async function () {
            var product_id = $("input[name='product_id']").val()
            var booking_type_id = $("input[name='booking_type_id']").val()
            if (this.product_month > 0) {
                this.product_month -= 1
                await this._rpc({
                    route: "/product-booking-slots",
                    params: {
                        booking_type: booking_type_id,
                        product_id: product_id,
                        month: this.product_month,
                    },
                }).then(res => {
                    $("#product_booking_calendar").replaceWith(res)
                })
            } else {
                alert("You cannot make booking for past months")
            }
        },

        _HighlightMultipleBookingSlots: function (event) {
            if (this.x_click > 1) {
                this.starting_slot;
                this.ending_slot;
                this.x_click = 0
            }

            if (this.x_click == 0) {
                this.starting_slot = $(event.target).data('bookingDateTime')
            } else {
                this.ending_slot = $(event.target).data('bookingDateTime')
            }

            this.x_click++

            if (this.starting_slot && this.ending_slot){
                $("#selected_slots").html('You have selected slots between: <strong>' + this.starting_slot + '</strong> --- <strong>' + this.ending_slot + '</strong>')
            }
            else if(this.starting_slot && typeof(this.ending_slot) === "undefined") {
                $("#selected_slots").html('You have selected: <strong>' + this.starting_slot + '</strong>')
            }
        },

        _BookProduct: function (event) {
            var clicked_slot = $(event.target)
            var product_id = $("input[name='product_id']").val()
            var booking_type_id = $("input[name='booking_type_id']").val()

            var params = {
                'product_id': product_id,
                'booking_type_id': booking_type_id,
                'start_date': this.starting_slot,
                'end_date': this.ending_slot,
            }

            if (this.starting_slot) {
                return wUtils.sendRequest('/shop/booking/update', params);
            }
            else {
                alert("You should select a booking date")
            }
        }
    });
});

