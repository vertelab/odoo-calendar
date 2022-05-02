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
    'name': 'Calendar ics-urls',
    'version': '14.0.0.0.0',
    # Version ledger: 14.0 = Odoo version. 1 = Major. Non regressionable code. 2 = Minor. New features that are regressionable. 3 = Bug fixes
    'summary': 'Subscription on calendar.ics-urls',
    'category': 'Customizations',
    'description': 'Adds and updates calendar objects according to an ics-url.',
    #'sequence': '1'
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar/calendar-ics',
    'images': ['/static/description/banner.png'], # 560x280 px.
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['calendar',],
    'external_dependencies': {
#        'python': ['icalendar', 'urllib2'],
        'python': ['icalendar', ],
    },
    'data': [ 'res_partner_view.xml',
    #'security/ir.model.access.csv',
    'res_partner_data.xml'
    ],
    'application': False,
    'installable': True,
    'demo': ['calendar_ics_demo.xml',],
}
# vim:expandtab:smartindent:tabstop=4s:softtabstop=4:shiftwidth=4:
