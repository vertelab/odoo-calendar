##############################################################################
#
#    Odoo, Open Source Management Solution
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
    'name': 'Calendar: Import holidays',
    'version': '18.0.1.0.2',
    # Version ledger: 14.0 = Odoo version. 1 = Major. Non regressionable code. 2 = Minor. New features that are regressionable. 3 = Bug fixes
    'summary': 'Import holidays will update monthly basis so you are always on the right.',
    'category': 'Calendar',
    'description': '''
Import holidays
===============

Import holidays into the calendar and every working schedule.

One URL pointing at an .ics file is imported. The events are mirrored into
``calendar.event`` and into ``resource.calendar.leaves`` on every working
schedule, so public holidays are not planned as working time. The import
re-runs monthly and only creates what is missing.

Requires the python library ``ics``.

Contributors
------------

* Vertel Sverige AB
    ''',
    #'sequence': '1',
    'author': 'Vertel Sverige AB',
    'website': 'https://vertel.se/apps/odoo-calendar/ics_import_holidays',
    'images': ['static/description/banner.png'], # 560x280 px.
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel Sverige AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['base_setup', 'calendar', 'hr', 'cron_tick'],
    'data': [
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "data/cron_tasks.xml",
        "data/users.xml",
    ],
    'external_dependencies': {
    'python': ['icalendar'],
    },
}
