# -*- coding: utf-8 -*-
{
    'name': 'Calendar: AI',
    'version': '18.0.1.1.0',
    'summary': 'OKF-indexering av kalenderhändelser (calendar.event)',
    'category': 'Productivity/Calendar',
    'author': 'Vertel Sverige AB',
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

        En händelse ger ett koncept per intressent: ett `company`-koncept
        ägt av händelsens företag, och ett `personal` per deltagare som är
        en användare. Deltagarlistan kapas i de personliga koncepten.

        KRAV PÅ KÄRNAN (calendar_okf-personal-company D3):
        `ai_agent_core` >= 18.0.1.302 krävs för `_okf_owner_vals_list()`
        (en post -> N ägare) och för `owner_vals`-argumentet i
        `_okf_summary_source()` (sammanfattning per ägare). Odoos manifest
        kan inte uttrycka ett modulversionskrav — `depends` är modulnamn.
        Kravet grindas därför av `tests/test_calendar_okf_contract.py`,
        som faller om kontraktet saknas.
    """,
    'depends': [
        'ai_agent_core',
        'calendar',
    ],
    'data': [
        'data/okf_artifact_types_calendar.xml',
        'data/okf_debug_actions.xml',
    ],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
}
