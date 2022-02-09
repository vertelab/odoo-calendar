odoo.define('website_calendar_ce.online_booking_options', function (require) {
    'use strict';

    var core = require('web.core');
    var options = require('web_editor.snippets.options');
    var rpc = require('web.rpc');
    var QWeb = core.qweb;

    var ajax = require('web.ajax');
    ajax.loadXML('/website_calendar_ce/static/src/xml/booking.xml', QWeb);


    options.registry.online_booking_options = options.Class.extend({

        events: _.extend({}, options.Class.prototype.events || {}, {
            'click we-button': '_onAddItemSelectClick',
        }),

        init: function() {
            const _super = this._super.bind(this);
            this.selected_booking_type = null;
            return _super(...arguments);
        },

        willStart: async function () {
            const _super = this._super.bind(this);

            var data = await this._rpc({
                model: 'calendar.booking.type',
                method: 'find_all_bookings',
            });
            this.booking_types = JSON.parse(data);
            this.active_booking_type = this.booking_types[0].id;

            this.selectProjectEl = document.createElement('we-select');
            this.selectProjectEl.setAttribute('string', 'Booking Type');

            this.booking_types.forEach(booking_type => {
                const option = document.createElement('we-button');
                option.textContent = booking_type.name;
                option.setAttribute('data-customize-website-variable', booking_type.name)
                option.dataset.selectAction = booking_type.id;
                this.selectProjectEl.append(option);
            });
            return _super(...arguments);
        },

        start: function () {
            this.$('#booking_header').append(QWeb.render('BookingType',
                {'booking_types': this.booking_types, 'active_booking_type': this.active_booking_type}
            ));
            this._CalendarTypeSelected()
            return this._super.apply(this, arguments);

        },

        _renderCustomXML: function(uiFragment) {
            // Add Action select
            const firstOption = uiFragment.childNodes[0];
            uiFragment.insertBefore(this.selectProjectEl.cloneNode(true), firstOption);
            return uiFragment;
        },

        _onAddItemSelectClick: function (ev) {
            /* On clink on we-button, update the active booking type */
            this.active_booking_type = ev.currentTarget.dataset.selectAction
            ev.currentTarget.classList.toggle('active');
            this._CalendarTypeSelected()
        },

        _CalendarTypeSelected: function () {
             /* update the calendar type form after we-button is clicked or widget start */
            console.log(typeof this.active_booking_type)
            this.$('#calendarType option').removeAttr('selected').filter(
                `[value=${this.active_booking_type}]`).attr('selected', true)
            this._BookingTypeEmployee(this.active_booking_type)
        },

        _BookingTypeEmployee: async function (booking_id) {
            /* Get Calendar booking type details and update the DOM with the active booking type*/
            var data = await this._rpc({
                model: 'calendar.booking.type',
                method: 'get_booking_details',
                args: [parseInt(booking_id)],
            });
            if (data) {
                data['active_booking_type'] = this.active_booking_type
                this.$('#employee_select').replaceWith(QWeb.render('BookingEmployees', data));
            }
            return true
        }
    });
})

