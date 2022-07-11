# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) {year} {company} (<{mail}>)
#    All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
#
# https://www.odoo.com/documentation/14.0/reference/module.html
#
{
    'name': 'Calendar Web Notifications',
    'version': '14.0.0.0.0',
    'summary': """
        Module enables you get push notifications when calendar events are created.""",
    'category': 'Calendar',
    'description': """
        Module enables you get push notifications when calendar events are created.
    """,
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar',
    'license': 'AGPL-3',
    'depends': ['mail', 'base', 'calendar', 'web_notify'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/firebase_config_view.xml',
    ],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
}
