# -*- coding: utf-8 -*-
{
    'name': 'Kalender & kontakter i Vertel',
    'version': '18.0.1.0.0',
    'summary': 'Onboardingskurs: kalender, kontakter och DAV-synk',
    'description': """
Lär dig synka kalender och adressbok mot mobil, Outlook och Thunderbird — och boka resurser.
""",
    'author': 'Vertel AB',
    'website': 'https://vertel.se',
    'license': 'LGPL-3',
    'category': 'Website/eLearning',
    'depends': ['website_slides'],
    'data': [
        'views/slide_channel_data.xml',
    ],
    'demo': [
        'demo/slide_slide_demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
