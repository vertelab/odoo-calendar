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
    'name': 'Calendar: Product Resource',
    'version': '14.0.0.0.1',
    'summary': 'Calendar Product Resource',
    'category': 'Calendar',
    'description': """
        Allow clients to Schedule Bookings through your Website
        -------------------------------------------------------
    """,
    'sequence': '131',
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar/website_calendar_product_resource',
    'images': ['static/description/banner.png'],  # 560x280 px.
    'license': 'AGPL-3',
    'maintainer': 'Vertel AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['product', 'resource', 'website_calendar_ce'],
    'data': [
        "data/website_calendar_data.xml",
        "views/product_view.xml",
        # "views/resource_view.xml",
        "views/calendar_booking_view.xml",
        "views/website_calendar_templates.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
