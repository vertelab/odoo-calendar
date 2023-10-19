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
    'name': 'Calendar: Website Calendar Slot Range',
    'version': '14.0.0.0.1',
    'summary': 'Booking a range of time slot',
    'category': 'Calendar',
    'description': """
        Allow clients to Booking a range of time slot
        -------------------------------------------------------
    """,
    'sequence': '131',
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar/website_calendar_slot_range',
    'images': ['static/description/banner.png'],  # 560x280 px.
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['website_calendar_ce'],
    'data': [
        'views/website_calendar_templates.xml'

    ],
    'assets': {
        'web.assets_frontend': [
            'website_calendar_slot_range/static/src/js/website_calendar_ce.js'
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
