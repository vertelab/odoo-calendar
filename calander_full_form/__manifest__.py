# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution, third party addon
#    Copyright (C) 2021- Vertel AB (<http://vertel.se>).
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
    'name': 'Calendar: Calender Full Form',
    'version': '14.0.0.0',
    'summary': 'To be able to open calendar form view instead of a popup.',
    'category': 'Calendar',
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-calendar/calender_full_form',
    'license': 'AGPL-3'
    https://github.com/vertelab/odoo-
    'description': """
        To be able to open calendar form view instead of a popup
    """,
    'depends': ['calendar'],
    'data': [
        'views/calendar_view.xml'
    ],
    'application': True,
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4s:softtabstop=4:shiftwidth=4:
