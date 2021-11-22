odoo.define('website_calendar_ce.booking_employee_url', function (require) {
'use strict';

/**
 * This module contains the booking_employee_url widget, created specifically to
 * display the direct employee url for a calendar.booking.type.
 *
 * It's set on the id field and will only exist in readonly mode.
 */

var AbstractField = require('web.AbstractField');
var core = require('web.core');
var fieldRegistry = require('web.field_registry');

var _t = core._t;

var FieldemployeeUrl = AbstractField.extend({
    events: _.extend({}, AbstractField.prototype.events, {
        'click .o_website_calendar_copy_icon': '_stopPropagation',
        'click .o_form_uri': '_stopPropagation',
    }),
    supportedFieldTypes: [],

    /**
     * This widget should only exist in readonly mode and its value is set to the url.
     * Its structure is a div containing a link and a "copy to clipboard" icon.
     *
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.tagName = 'div';

        this.url = false;
        var base_url = this.getSession()['web.base.url'];
        var bookingURL = this.record.getContext({fieldName: 'id'}).url;
        if (bookingURL) {
            this.url = base_url + bookingURL.replace("/booking", "") + '?employee_id=' + this.value;
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * The widget needs to be a link with proper href and a clipboard
     * icon that saves the url to the clipboard, classes are added for
     * proper design.
     *
     * @override
     * @private
     */
    _render: function () {
        if(!this.url) {
            return;
        }
        var $link = $('<a>', {
            class: 'o_form_uri fa-o_text_overflow',
            href: this.url,
            text: this.url,
        });
        var $icon = $('<div>', {
            class: 'fa fa-clipboard o_website_calendar_copy_icon'
        });

        $icon.tooltip({title: _t("Copied !"), trigger: "manual", placement: "right"});
        var clipboard = new window.ClipboardJS($icon[0], {
            text: this.url.trim.bind(this.url),
            container: this.el,
        });
        clipboard.on("success", function (e) {
            _.defer(function () {
                $icon.tooltip("show");
                _.delay(function () {
                    $icon.tooltip("hide");
                }, 800);
            });
        });

        this.$el.empty()
                .append($link)
                .append($icon);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Stop the propagation of the event.
     * On this widget, clicks should only open a link or copy the url to the
     * clipboard. Prevent the opening of the form view if in a list view.
     *
     * @private
     * @param {MouseEvent} event
     */
     _stopPropagation: function (ev) {
        ev.stopPropagation();
    },
});

fieldRegistry.add('booking_employee_url', FieldemployeeUrl)
});
