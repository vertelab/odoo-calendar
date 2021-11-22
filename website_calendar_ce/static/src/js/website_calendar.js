odoo.define('website_calendar_ce.select_booking_type', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

publicWidget.registry.websiteCalendarSelect = publicWidget.Widget.extend({
    selector: '.o_website_calendar_booking',
    events: {
        'change .o_website_booking_form select[id="calendarType"]': '_onBookingTypeChange'
    },

    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        // Check if we cannot replace this by a async handler once the related
        // task is merged in master
        this._onBookingTypeChange = _.debounce(this._onBookingTypeChange, 250);
    },
    /**
     * @override
     * @param {Object} parent
     */
    start: function (parent) {
        // set default timezone
        var timezone = jstz.determine();
        $(".o_website_appoinment_form select[name='timezone']").val(timezone.name());
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
});
});

//==============================================================================

odoo.define('website_calendar_ce.booking_form', function (require) {
'use strict';

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

odoo.define('website_calendar_ce.booking_website_form', function (require) {
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
});
