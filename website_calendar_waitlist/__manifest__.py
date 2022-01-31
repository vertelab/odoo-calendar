# -*- coding: utf-8 -*-

{
    'name': 'Website Calendar Waitlist',
    'version': '1.0',
    'category': 'Marketing/Online Appointment',
    'sequence': 131,
    'summary': 'Schedule bookings with clients',
    'website': 'https://vertel.se/apps/website_calendar_event',
    'description': """
TODO:
""",
    'depends': ['website_calendar_ce', 'website_calendar_event', 'hr', 'base'],
    'data': [
        'views/calendar_booking_views.xml',
        'views/website_waitlist_templates.xml',
        'views/project_portal_templates.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
