odoo.define('website_booking_checkout.booking_actions', function (require) {
    'use strict';


    var publicWidget = require('web.public.widget');

    var core = require('web.core');
    var config = require('web.config');
    var publicWidget = require('web.public.widget');
    var VariantMixin = require('sale.VariantMixin');
    var wSaleUtils = require('website_sale.utils');
    const wUtils = require('website.utils');
    require("web.zoomodoo");


    publicWidget.registry.WebsiteBookingCheckout = publicWidget.Widget.extend({
        selector: '.o_website_product_booking',
        events: {
//            'change select[id="product_calendarType"]': "_onChangeProductBookingType",
            'click #product_previous_month': '_onPreviousMonth',
            'click #product_next_month': '_onNextMonth',
            'click td.dropdown > div.dropdown-menu > a': '_HighlightMultipleBookingSlots',
            'click #proceed_with_booking': '_BookProduct'
        },

        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
//            this._onChangeProductBookingType = _.debounce(this._onChangeProductBookingType, 250);
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

        /**
         * On booking type change: adapt booking intro text and available
         * employees (if option enabled)
         *
         * @override
         * @param {Event} ev
         */
//        _onChangeProductBookingType: function (ev) {
//            var bookingID = $(ev.target).val();
//            console.log("bookingID", bookingID)
//            var previousSelectedProductID = $(".o_website_appointment_form select[name='product_id']").val();
//            console.log("previousSelectedProductID", previousSelectedProductID)
//            var postURL = '/website/calendar/product/' + bookingID + '/booking';
//            console.log("postURL", postURL)
//            $(".o_website_appointment_form").attr('action', postURL);
//            this._rpc({
//                route: "/website/calendar/get_product_booking_info",
//                params: {
//                    booking_id: bookingID,
//                    prev_emp: previousSelectedProductID,
//                },
//            }).then(function (data) {
//                if (data) {
//                    $('.o_calendar_intro').html(data.message_intro);
//                    if (data.assignation_method === 'chosen') {
//                        $(".o_website_appointment_form div[name='product_select']").replaceWith(data.product_selection_html);
//                    } else {
//                        $(".o_website_appointment_form div[name='product_select']").addClass('o_hidden');
//                        $(".o_website_appointment_form select[name='product_id']").children().remove();
//                    }
//                }
//            });
//        },

        _onNextMonth: async function () {
            var product_id = $("input[name='product_id']").val()
            console.log("product_id", product_id)
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
                        $("#booking_calendar").replaceWith(res)
                    }
                })
            }
        },
//
        _onPreviousMonth: async function () {
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
                    $("#booking_calendar").replaceWith(res)
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

            console.log("product_id", product_id)
            console.log("booking_id", booking_type_id)

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

