{
    'name': "Website Booking Calendar",
    'version': "1.0.3",
    'author': "Odoobiz <info@odoobiz.com>",
    'category': "Tools",
    'summary': "Allow website users to book meetings from the website",
    'license':'LGPL-3',
    'description': """
Website Booking Calendar
=======================================
This theme has been upgraded for v10 from https://apps.odoo.com/apps/modules/9.0/website_calendar_booking/.

""",
    'data': [
        'views/website_calendar_views.xml',
        'views/website_calendar_booking_templates.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [],
    'depends': ['website', 'calendar'],
    'images': ['static/images/main.jpg'],
    'installable': True,
}