# -*- coding: utf-8 -*-

{
    'name': 'Website Calendar Event',
    'version': '1.0',
    'category': 'Marketing/Online Appointment',
    'sequence': 131,
    'summary': 'Schedule bookings with clients',
    'website': 'https://vertel.se/apps/website_calendar_event',
    'description': """

TODO:
""",
    'depends': ['website_calendar_ce', 'project'],

    'data': [
        'views/calendar_booking_views.xml',
        'views/project.xml',
        'views/project_portal_templates.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
