# -*- coding: utf-8 -*-
{
    'name': "l10n_se_calendar",

    'summary': 'Adds swedish holidays and dates of interest to your calendar.',

    'description': """
        Adding swedish holidays and important dates for Skatteverket
        
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
    'depends': ['calendar_ics'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'res_partner_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        #~ 'demo.xml',
    ],
}
