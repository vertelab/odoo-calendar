# -*- coding: utf-8 -*-

{
    'name': 'Website Calendar',
    'version': '1.0',
    'category': 'Marketing/Online Appointment',
    'sequence': 131,
    'summary': 'Schedule bookings with clients',
    'website': 'https://vertel.se/apps/website_calendar_ce',
    'description': """
Allow clients to Schedule Bookings through your Website
-------------------------------------------------------

""",
    'depends': ['calendar_sms', 'hr', 'website'],
    'data': [
        'data/website_calendar_data.xml',
        'views/calendar_views.xml',
        'views/calendar_booking_views.xml',
        'views/website_calendar_templates.xml',
        'security/website_calendar_security.xml',
        'security/ir.model.access.csv',
        'views/snippets/snippets.xml',
    ],
    'demo': [
        'data/website_calendar_demo.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
