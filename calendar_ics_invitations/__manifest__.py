# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo SA, Open Source Management Solution, third party addon
#    Copyright (C) 2026 Vertel Sverige AB (<https://vertel.se>).
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
# https://www.odoo.com/documentation/18.0/reference/module.html
#

{
    'name': 'Calendar: ICS Invitations',
    'version': '18.0.1.0.0',
    # Version ledger: 18.0 = Odoo version. 1 = Major. 0 = Minor. 0 = Bug fixes.
    'summary': 'Outlook/Teams compatible iTIP meeting invitations and cancellations',
    'category': 'Calendar',
    'description': '''
Calendar: ICS Invitations
=========================

Odoo core builds meeting invitations with a non-compliant iTIP payload: no
``METHOD``, a ``UID`` containing spaces, bare ``ATTENDEE`` lines and no
``SEQUENCE``. Microsoft Outlook/Exchange and Microsoft Teams therefore treat
the invitation as a static ``METHOD:PUBLISH`` entry, so recipients get no
Accept/Decline/Tentative buttons and a reschedule arrives as a new entry.

This module overrides ``calendar.event._get_ics_file()`` so the generated
``VEVENT`` is Outlook/Exchange/Teams compatible:

    - ``METHOD:REQUEST`` (invitation/update) or ``METHOD:CANCEL`` (cancellation)
    - a stable, space-free ``UID`` persisted on the event
    - a persisted ``SEQUENCE`` incremented on scheduling-relevant changes
    - ``ORGANIZER`` and ``ATTENDEE`` lines with ``CN``, ``ROLE``, ``PARTSTAT``
      and ``RSVP``, using a lowercase ``mailto:`` scheme
    - Exchange-compatible ``STATUS``, ``TRANSP``, ``CLASS``, ``DTSTAMP`` and
      ``LAST-MODIFIED``

Distribution of attendee responses (accepted/declined/tentative) to the other
attendees is handled together with ``extended_calendar_notifications``.

The mail templates, recipient selection and attachment naming of the
invitation, update and cancellation flows are left untouched.
    ''',
    'author': 'Vertel Sverige AB',
    'website': 'https://vertel.se/apps/odoo-calendar/calendar_ics_invitations',
    'images': ['static/description/banner.png'],  # 560x280 px.
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel Sverige AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['calendar', 'mail', 'extended_calendar_notifications'],
    'data': [],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
}
