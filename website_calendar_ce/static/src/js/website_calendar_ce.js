/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { debounce, Deferred } from "@bus/workers/websocket_worker_utils";


publicWidget.registry.websiteCalendarSelect = publicWidget.Widget.extend({
    selector: '.o_website_calendar',
    events: {
        'change select[id="calendarType"]': "_onBookingTypeChange",
        'click #previous_month': '_onPreviousMonth',
        'click #next_month': '_onNextMonth',
    },

    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        // Check if we cannot replace this by a async handler once the related
        // task is merged in master
        this._onBookingTypeChange = debounce(this._onBookingTypeChange, 250);
        this.month = 0;
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
    _onBookingTypeChange: function (ev) {
        var bookingID = $(ev.target).val();
        var previousSelectedEmployeeID = $(".o_website_appointment_form select[name='employee_id']").val();
        var postURL = '/website/calendar/' + bookingID + '/booking';
        $(".o_website_appointment_form").attr('action', postURL);
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
                    $(".o_website_appointment_form div[name='employee_select']").replaceWith(data.employee_selection_html);
                } else {
                    $(".o_website_appointment_form div[name='employee_select']").addClass('o_hidden');
                    $(".o_website_appointment_form select[name='employee_id']").children().remove();
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
});


//==============================================================================

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



