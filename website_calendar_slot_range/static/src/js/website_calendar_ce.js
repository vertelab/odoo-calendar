odoo.define('website_calendar_slot_range.multiple_slot', function (require) {
    'use strict';


    var publicWidget = require('web.public.widget');

    publicWidget.registry.MultipleSlot = publicWidget.Widget.extend({
        selector: '.o_website_calendar',
        events: {
            'click td.dropdown > div.dropdown-menu > a': '_HighlightMultipleSlots'
        },

        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
            // Check if we cannot replace this by a async handler once the related
            // task is merged in master
            this.x_click = 0;
            this.starting_slot;
            this.ending_slot;
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

         _HighlightMultipleSlots: function (event) {
            var clicked_slot = $(event.target)
            var booking_id = $(event.target).data('bookingId')
            var employee_id = $(event.target).data('employeeId')
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

