odoo.define('website_calendar_product_resource.select_booking_type', function (require) {
    'use strict';


    var publicWidget = require('web.public.widget');

    publicWidget.registry.websiteCalendarProductSelect = publicWidget.Widget.extend({
        selector: '.o_website_calendar',
        events: {
            'change select[id="product_calendarType"]': "_onChangeProductBookingType",
            'click #product_previous_month': '_onPreviousMonth',
            'click #product_next_month': '_onNextMonth',
            'click td.dropdown > div.dropdown-menu > a': '_HighlightMultipleSlots'
        },

        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
            // Check if we cannot replace this by a async handler once the related
            // task is merged in master
            this._onChangeProductBookingType = _.debounce(this._onChangeProductBookingType, 250);
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
            // set default timezone
            // TODO: This does not seem to work, as jstz is not available
            /**
             *
             * var timezone = jstz.determine();
             * $(".o_website_appoinment_form select[name='timezone']").val(timezone.name());
             *
             */
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
        _onChangeProductBookingType: function (ev) {
            var bookingID = $(ev.target).val();
            console.log("bookingID", bookingID)
            var previousSelectedProductID = $(".o_website_appointment_form select[name='product_id']").val();
            console.log("previousSelectedProductID", previousSelectedProductID)
            var postURL = '/website/calendar/product/' + bookingID + '/booking';
            console.log("postURL", postURL)
            $(".o_website_appointment_form").attr('action', postURL);
            this._rpc({
                route: "/website/calendar/get_product_booking_info",
                params: {
                    booking_id: bookingID,
                    prev_emp: previousSelectedProductID,
                },
            }).then(function (data) {
                if (data) {
                    $('.o_calendar_intro').html(data.message_intro);
                    if (data.assignation_method === 'chosen') {
                        $(".o_website_appointment_form div[name='product_select']").replaceWith(data.product_selection_html);
                    } else {
                        $(".o_website_appointment_form div[name='product_select']").addClass('o_hidden');
                        $(".o_website_appointment_form select[name='product_id']").children().remove();
                    }
                }
            });
        },

        _onNextMonth: async function () {
            var product_id = $("input[name='product_id']").val()
            console.log("product_id", product_id)
            var booking_type_id = $("input[name='booking_type_id']").val()
            var self = this;

            if (product_id && booking_type_id) {
                await this._rpc({
                    route: "/booking/product/slots",
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

        _onPreviousMonth: async function () {
            var product_id = $("input[name='product_id']").val()
            var booking_type_id = $("input[name='booking_type_id']").val()
            if (this.product_month > 0) {
                this.product_month -= 1
                await this._rpc({
                    route: "/booking/product/slots",
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

        formatDate: function (datetime) {
            const year = datetime.getFullYear();
            const month = String(datetime.getMonth() + 1).padStart(2, '0');
            const day = String(datetime.getDate()).padStart(2, '0');
            const hours = String(datetime.getHours()).padStart(2, '0');
            const minutes = String(datetime.getMinutes()).padStart(2, '0');
            const seconds = String(datetime.getSeconds()).padStart(2, '0');
            return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        },

        _HighlightMultipleSlots: function (event) {
            var clicked_slot = $(event.target)
            var booking_id = $(event.target).data('bookingId')
            var product_id = $(event.target).data('productId')
            var description = $(event.target).data('description')
            var title = $(event.target).data('title')

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
                var booking_url = `/website/calendar/${booking_id}/product/info?product_id=${product_id}&start_date=${this.starting_slot}&end_date=${this.ending_slot}&description=${description}&title=${title}`
                $("#proceed_with_slot").attr("href", booking_url)
            }
            else if(this.starting_slot && typeof(this.ending_slot) === "undefined") {
                var starting_slot_date = new Date(this.starting_slot);
                starting_slot_date.setMinutes(starting_slot_date.getMinutes() + 30);
                this.ending_slot = this.formatDate(new Date(starting_slot_date.toLocaleString()));

                $("#selected_slots").html('You have selected: <strong>' + this.starting_slot + '</strong>')

                var booking_url = `/website/calendar/${booking_id}/product/info?product_id=${product_id}&start_date=${this.starting_slot}&end_date=${this.ending_slot}&description=${description}&title=${title}`

//                var booking_url = `/website/calendar/${booking_id}/info?product_id=${product_id}&start_date=${this.starting_slot}&description=${description}&title=${title}`
                $("#proceed_with_slot").attr("href", booking_url)
            }
        }
    });
});

