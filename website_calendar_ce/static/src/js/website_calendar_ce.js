

odoo.define('website_calendar_ce.select_booking_type', function (require) {
    'use strict';


    var publicWidget = require('web.public.widget');

    publicWidget.registry.websiteCalendarSelect = publicWidget.Widget.extend({
        selector: '.o_website_calendar',
        events: {
            'change select[id="calendarType"]': "_onBookingTypeChange",
            'click #previous_month': '_onPreviousMonth',
            'click #next_month': '_onNextMonth',
            'click td.dropdown > div.dropdown-menu > a': '_HighlightMultipleSlots'
        },

        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
            // Check if we cannot replace this by a async handler once the related
            // task is merged in master
            this._onBookingTypeChange = _.debounce(this._onBookingTypeChange, 250);
            this.month = 0;
            this.x_click = 1;
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
        _onBookingTypeChange: function (ev) {
            var bookingID = $(ev.target).val();
            var previousSelectedEmployeeID = $(".o_website_appoinment_form select[name='employee_id']").val();
            var postURL = '/website/calendar/' + bookingID + '/booking';
            $(".o_website_appoinment_form").attr('action', postURL);
            this._rpc({
                route: "/website/calendar/get_booking_info",
                params: {
                    booking_id: bookingID,
                    prev_emp: previousSelectedEmployeeID,
                },
            }).then(function (data) {
                if (data) {
                    $('.o_calendar_intro').html(data.message_intro);
                    if (data.assignation_method === 'chosen') {
                        $(".o_website_appoinment_form div[name='employee_select']").replaceWith(data.employee_selection_html);
                    } else {
                        $(".o_website_appoinment_form div[name='employee_select']").addClass('o_hidden');
                        $(".o_website_appoinment_form select[name='employee_id']").children().remove();
                    }
                }
            });
        },

        _onNextMonth: async function () {
            var employee_id = $("input[name='employee_id']").val()
            var booking_type_id = $("input[name='booking_type_id']").val()
            var self = this;

            if (employee_id && booking_type_id) {
                await this._rpc({
                    route: "/booking/slots",
                    params: {
                        booking_type: booking_type_id,
                        employee_id: employee_id,
                        month: this.month + 1,
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

        _onPreviousMonth: async function () {
            var employee_id = $("input[name='employee_id']").val()
            var booking_type_id = $("input[name='booking_type_id']").val()
            if (this.month > 0) {
                this.month -= 1
                await this._rpc({
                    route: "/booking/slots",
                    params: {
                        booking_type: booking_type_id,
                        employee_id: employee_id,
                        month: this.month,
                    },
                }).then(res => {
                    $("#booking_calendar").replaceWith(res)
                })
            } else {
                alert("You cannot make booking for past months")
            }
        },

        _HighlightMultipleSlots: function (event) {
            var clicked_slot = $(event.target)
            var booking_id = $(event.target).data('bookingId')
            var employee_id = $(event.target).data('employeeId')
            var description = $(event.target).data('description')
            var title = $(event.target).data('title')

            if (this.x_click === 2 || this.x_click < 0) {
                this.x_click = 0
            }
            if (this.x_click == 1) {
                this.starting_slot = $(event.target).data('bookingDateTime')
            } else {
                this.ending_slot = $(event.target).data('bookingDateTime')
            }

             if (new Date(this.ending_slot) <= new Date(this.starting_slot)) {
                this.x_click = 1
                return alert("You cannot book between past slots")
            }

            this.x_click++

            if (this.starting_slot && this.ending_slot){
                $("#selected_slots").html('You have selected slots between: <strong>' + this.starting_slot + '</strong> --- <strong>' + this.ending_slot + '</strong>')
                var booking_url = `/website/calendar/${booking_id}/info?employee_id=${employee_id}&start_date=${this.starting_slot}&end_date=${this.ending_slot}&description=${description}&title=${title}`
                $("#proceed_with_slot").attr("href", booking_url)
            }
            else if(this.starting_slot && typeof(this.ending_slot) === "undefined") {
                $("#selected_slots").html('You have selected: <strong>' + this.starting_slot + '</strong>')
                var booking_url = `/website/calendar/${booking_id}/info?employee_id=${employee_id}&start_date=${this.starting_slot}&description=${description}&title=${title}`
                $("#proceed_with_slot").attr("href", booking_url)
            }
        }
    });
});

//==============================================================================

odoo.define('website_calendar_ce.booking_form', function (require) {
    'use strict';

    // TODO: This entire event handler seems to be unused, some other function is updating the
    // data we are interested in

    var publicWidget = require('web.public.widget');

    publicWidget.registry.websiteCalendarForm = publicWidget.Widget.extend({
        selector: '.o_website_calendar_form',
        events: {
            'change .booking_submit_form select[name="country_id"]': '_onCountryChange',
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * @override
         * @param {Event} ev
         */
        _onCountryChange: function (ev) {
            var countryCode = $(ev.target).find('option:selected').data('phone-code');
            $('.booking_submit_form #phone_field').val(countryCode);
        },
    });
});

// TODO: This event handler require 'animation' which is not available using the required modules
// currently set up.

/*odoo.define('website_calendar_ce.booking_website_form', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var websiteFormWidget = require('website_form.animation');

publicWidget.registry.websiteCalendarFormChecker = websiteFormWidget.extend({
    selector: '.o_website_calendar_form',

    post_form: function(form_values) {
        // call default submit behavior
        this.$target.find('.booking_submit_form').submit()
    },
});
});*/
