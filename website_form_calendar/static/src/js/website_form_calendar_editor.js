odoo.define('website_form_calendar.form', function (require) {
    'use strict';

    var core = require('web.core');
    var FormEditorRegistry = require('website_form.form_editor_registry');

    var _t = core._t;

    FormEditorRegistry.add('create_calendar', {
        formFields: [{
            type: 'char',
            custom: true,
            required: true,
            name: 'Your Name',
        }, {
            type: 'char',
            custom: true,
            name: 'Your Company',
        }, {
            type: 'email',
            custom: true,
            modelRequired: true,
            name: 'Your Email',
        }, {
            type: 'tel',
            custom: true,
            name: 'Your Phone',
        }, {
            type: 'text',
            custom: true,
            required: true,
            name: 'Comment',
        }],
        fields: [{
            name: 'booking_type_id',
            type: 'many2one',
            relation: 'calendar.booking.type',
            string: _t('Booking'),
        }],
    });

});
