# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo SA, Open Source Management Solution, third party addon
#    Copyright (C) 2022- Vertel AB (<https://vertel.se>).
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
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Calendar: Website Calendar',
    'version': '14.0.0.0.1',
    # Version ledger: 14.0 = Odoo version. 1 = Major. Non regressionable code. 2 = Minor. New features that are regressionable. 3 = Bug fixes
    'summary': 'Schedule bookings with clients',
    'category': 'Calendar',
    'description': """
    Allow clients to Schedule Bookings through your Website
    -------------------------------------------------------
    """,
    'sequence': '131',
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar/website_calendar_ce',
    'images': ['static/description/banner.png'],  # 560x280 px.
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['calendar_sms', 'hr', 'website', 'mail'],
    'data': [
        'data/website_calendar_data.xml',
        'views/calendar_views.xml',
        'views/calendar_booking_views.xml',
        'views/website_calendar_templates.xml',
        'security/website_calendar_security.xml',
        'security/ir.model.access.csv',

        # 'views/snippets/snippets.xml',

    ],
    'demo': [
        'data/website_calendar_demo.xml'
    ],
    # 'qweb': [
    #     'static/src/xml/booking.xml',
    # ],
    'external_dependencies': {
        'python': [
            'pandas'  # sudo pip3 install pandas
        ]
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
