# Copyright (C) 2026 Vertel Sverige AB (<https://vertel.se>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Calendar: Onboarding (LMS)',
    'version': '18.0.3.0.0',
    'summary': 'Onboardingskurs: kalender, kontakter och DAV-synk',
    'description': """
Kalender & kontakter i Vertel
=============================

Onboardingskurs som lär ut hur kalender och adressbok synkroniseras mot
mobil, Outlook och Thunderbird — och hur resurser bokas.

5 sektioner, 17 slides (9 article, 1 infographic, 5 quiz):

- Sektion 1: Grunderna — CalDAV, CardDAV och hur det hänger ihop i Vertel
- Sektion 2: Koppla mobilen — DAVx⁵ på Android, inbyggt stöd i iOS
- Sektion 3: Adressböcker — företagets gemensamma och din privata lista
- Sektion 4: Skrivbordet och resursbokning — Thunderbird, Outlook, rum och utrustning
- Sektion 5: Manuellt test — verifiera tvåvägssynken steg för steg

Innehållet ligger i data/ (inte demo/) så att det laddas i alla databaser.
    """,
    'author': 'Vertel Sverige AB',
    'website': 'https://vertel.se/apps/odoo-calendar/calendar_onboarding',
    'license': 'AGPL-3',
    'category': 'Website/eLearning',
    'depends': ['website_slides'],
    'data': [
        'data/slide_channel.xml',
        'data/slide_slides_s1.xml',
        'data/slide_slides_s2.xml',
        'data/slide_slides_s3.xml',
        'data/slide_slides_s4.xml',
        'data/slide_slides_s5.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
