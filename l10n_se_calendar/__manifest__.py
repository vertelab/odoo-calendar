# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Enterprise Management Solution, third party addon
#    Copyright (C) 2018- Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
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
