odoo.define('website_calendar_ce.editor', function (require) {
'use strict';

var core = require('web.core');
var wUtils = require('website.utils');
var WebsiteNewMenu = require('website.newMenu');

var _t = core._t;

WebsiteNewMenu.include({
    actions: _.extend({}, WebsiteNewMenu.prototype.actions || {}, {
        new_booking: '_createNewBooking',
    }),

    //--------------------------------------------------------------------------
    // Actions
    //--------------------------------------------------------------------------

    /**
     * Asks the user information about a new booking type to create,
     * then creates it and redirects the user to this new booking type.
     *
     * @private
     * @returns {Promise} Unresolved if there is a redirection
     */
    _createNewBooking: function () {
        var self = this;
        return wUtils.prompt({
            window_title: _t("New Booking Type"),
            input: _t("Name"),
        }).then(function (result) {
            var name = result.val;
            if (!name) {
                return;
            }
            return self._rpc({
                model: 'calendar.booking.type',
                method: 'create_and_get_website_url',
                args: [[]],
                kwargs: {
                    name: name,
                },
            }).then(function (url) {
                window.location.href = url;
                return new Promise(function () {});
            });
        });
    },
});

});
