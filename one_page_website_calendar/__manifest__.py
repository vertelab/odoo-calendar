# -*- coding: utf-8 -*-

{
    'name': 'One Page Website Calendar',
    'version': '1.0',
    'category': 'Marketing/Online Appointment',
    'sequence': 131,
    'summary': 'Schedule bookings with clients',
    'website': 'https://vertel.se/apps/one_page_website_calendar',
    'description': """
        Allow clients to Schedule Bookings through your Website
        -------------------------------------------------------
    """,
    'depends': ['calendar_sms', 'hr', 'website', 'website_calendar_ce'],
    'data': [
        'views/assets.xml',
        'views/snippet.xml',
    ],
    'qweb': [
        'static/src/xml/booking.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
