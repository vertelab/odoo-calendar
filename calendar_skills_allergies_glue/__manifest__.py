{
    'name': 'Calendar: Skills and allergies glue module',
    'version': '14.0.0.1.0',
    'category': 'Calendar',
    'summary': 'Compare contract and partner skills & allergies',
    'licence': 'AGPL-3',
    'description': """
    Adds a check if sklls and allergies match for a calendar.attendee
    """,
    'author': 'Vertel AB',
    'website': 'http://www.vertel.se',
    'depends': ['calendar_attendee_planning', 'contract_attendee', 'contract_allergic', 'contract_cleaner', 'contract'],
    'data': [
        'views/calendar_view.xml',
    ],
    'auto_install': True,
}