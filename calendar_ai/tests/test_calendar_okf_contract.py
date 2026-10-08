# -*- coding: utf-8 -*-
"""Kontraktet mot kärnan finns (calendar-okf, task 6.1).

VARFÖR: bryggan förutsätter `ai_agent_core` >= 18.0.1.302 —
`_okf_owner_vals_list()` (en post -> N ägare) och `owner_vals`-argumentet i
`_okf_summary_source()` (sammanfattning per ägare). Odoos manifest kan inte
uttrycka ett modulversionskrav (`depends` är modulnamn), så kravet grindas
här i stället: testet faller om kontraktet saknas.

Utan kontraktet skulle bryggan tyst falla tillbaka på ETT koncept per
händelse (company) — den gamla defekten — eller krascha på `owner_vals=`.
"""

from odoo.tests import common, tagged


@tagged('calendar_ai', 'okf', 'post_install', '-at_install')
class TestCalendarOkfContract(common.TransactionCase):
    """Kärnans ägarkontrakt finns på plats."""

    def test_owner_vals_list_exists(self):
        """`_okf_owner_vals_list()` finns på mixinen."""
        Mixin = self.env['ai.okf.mixin']
        self.assertTrue(
            hasattr(Mixin, '_okf_owner_vals_list'),
            'ai_agent_core >= 18.0.1.302 krävs: _okf_owner_vals_list() '
            'saknas. Utan den kan en post inte bli fler än ett koncept.')

    def test_owner_vals_list_default_is_single_owner(self):
        """Default-listan har exakt ett element (beteendet är bevarat)."""
        mem = self.env['ai.personal.memory'].new({})
        owners = mem._okf_owner_vals_list()
        self.assertEqual(len(owners), 1)

    def test_summary_source_accepts_owner_vals(self):
        """`_okf_summary_source()` tar emot `owner_vals`."""
        import inspect
        params = inspect.signature(
            type(self.env['calendar.event'])._okf_summary_source).parameters
        self.assertIn(
            'owner_vals', params,
            'ai_agent_core >= 18.0.1.302 krävs: _okf_summary_source() tar '
            'inte owner_vals. Utan den kan deltagarlistan inte kapas i '
            'personliga koncept.')

    def test_build_summary_accepts_owner_vals(self):
        """`_okf_build_summary()` skickar ägaren vidare."""
        import inspect
        params = inspect.signature(
            type(self.env['ai.okf.mixin'])._okf_build_summary).parameters
        self.assertIn('owner_vals', params)
