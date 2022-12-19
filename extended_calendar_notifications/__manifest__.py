
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
#
# https://www.odoo.com/documentation/14.0/reference/module.html
#

{
    'name': 'Calendar: Extended Notifications',
    'version': '14.0.0.0.1',
    # Version ledger: 14.0 = Odoo version. 1 = Major. Non regressionable code. 2 = Minor. New features that are regressionable. 3 = Bug fixes
    'summary': 'Module extends functionality for calandar events.',
    'category': 'Calendar',
    'description': """
    Module extends functionality for calandar events to send update emails when the event is deleted or changed.
    """,
    #'sequence': '1',
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar/extended_calendar_notifications',
    'images': ['static/description/banner.png'], # 560x280 px.
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['mail', 'base', 'calendar'],
     #"external_dependencies": {
     #   "bin": ["openssl",],
     #   "python": ["acme_tiny", "IPy",],
     #},
    'data': [
        'data/mail_template.xml'
    ],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
    #"post_init_hook": "post_init_hook",
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
