# -*- coding: utf-8 -*-
{
    'name': "l10n_se_calendar",

    'summary': 'Adds swedish holidays and dates of interest to your calendar.',

    'description': """

    Adds swedish holidays to the calendar
    Adds important tax declaration dates


    Todo:
    - install the actual calendar at install-time (now you have to "check" the url or wait for the cron job)
    - The tax declarations dates varies by type of company, add a logic to choose correct url
    - Add a nice icon for the module


        Swedish holidays thanks to Mozilla
        Skatterverks-dates thanks to Compiled AB and http://www.skatteverketkalender.se/

    """,

    'author': "Vertel AB",
    'website': "http://www.vertel.se",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['calendar_ics', 'account'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'res_partner_data.xml',
        'res_config_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        #~ 'demo.xml',
    ],
}
