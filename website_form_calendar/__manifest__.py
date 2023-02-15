# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Calendar: Online Booking Form',
    'category': 'Website/Website',
    'summary': 'Add a task suggestion form to your website',
    'version': '1.0',
    'description': """
        Generate form in Calendar app from a form published on your website. This module requires the use of the *Form Builder* module (available in Odoo Enterprise) in order to build the form.
    """,
    'depends': ['website_form', 'calendar', 'website_calendar_ce'],
    'data': [
        'data/website_calendar_data.xml',
        'views/website_form_calendar_assets.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'LGPL-3',
}
