# -*- coding: utf-8 -*-
{
    'name': 'Calendar: AI',
    'version': '18.0.1.0.0',
    'summary': 'OKF-indexering av kalenderhändelser (calendar.event)',
    'category': 'Productivity/Calendar',
    'author': 'Vertel AB',
    'website': 'https://vertel.se',
    'license': 'AGPL-3',
    'description': """
        Bryggmodul för OKF-indexering av kalendern.

        Lägger `ai.okf.mixin` på calendar.event så att händelser blir
        OKF-koncept: taggar, länkar, en kopia av texten (okf_body) och en
        sammanfattning (okf_summary) som embeddas och söks.

        En händelse är tidsbunden: namn, datum och deltagare är det som
        gör den sökbar. Modellen sammanfattar sig SJÄLV — en LLM hade
        formulerat om samma fakta olika varje gång.
    """,
    'depends': [
        'ai_agent_core',
        'calendar',
    ],
    'data': [
        'data/okf_artifact_types_calendar.xml',
    ],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
}
