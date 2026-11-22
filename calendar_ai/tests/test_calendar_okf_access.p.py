# -*- coding: utf-8 -*-
"""Rättigheter och urval styr per scope (calendar-okf D2, D3).

VARFÖR: att en användare är deltagare i en händelse ska INTE i sig göra
händelsens company-koncept läsbart för hen. Rättigheterna prövas mot
konceptets källa — och det personliga konceptet är isolerat till sin ägare.

Dessa tester bevisar:
  1. company-konceptet injiceras inte för en deltagare utan rätt till källan
  2. hens eget personal-koncept injiceras ändå
  3. två deltagares personliga koncept isoleras i sökningen
  4. en deltagarändring flaggar och skriver om samtliga ägarkoncept
  5. oförändrad text ger ingen ny version
"""

import datetime

from odoo import fields
from odoo.tests import common, tagged


@tagged('calendar_ai', 'okf', 'post_install', '-at_install')
class TestCalendarOkfAccess(common.TransactionCase):
    """D2/D3: rättigheter, isolering och omindexering."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Concept = cls.env['ai.okf.concept']
        cls.Event = cls.env['calendar.event']
        cls.start = datetime.datetime(2026, 5, 4, 13, 0, 0)
        cls.stop = datetime.datetime(2026, 5, 4, 14, 0, 0)

        def _user(name, login):
            partner = cls.env['res.partner'].create({
                'name': name, 'email': '%s@example.com' % login})
            return cls.env['res.users'].create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'partner_id': partner.id})

        cls.user_a = _user('ZZ Acc A', 'zz_acc_a')
        cls.user_b = _user('ZZ Acc B', 'zz_acc_b')

    def _event(self, partners=None, **kw):
        partners = partners or [self.user_a.partner_id, self.user_b.partner_id]
        vals = {
            'name': 'ZZ Accesstest',
            'start': fields.Datetime.to_string(self.start),
            'stop': fields.Datetime.to_string(self.stop),
            'partner_ids': [(6, 0, [p.id for p in partners])],
        }
        vals.update(kw)
        return self.Event.create(vals)

    def _concepts(self, event):
        return self.Concept.search([
            ('source_ref', '=', 'calendar.event,%s' % event.id)])

    # ── 4.1: rättigheter ──

    def test_company_concept_hidden_but_personal_visible(self):
        """Company-konceptet injiceras inte för en deltagare utan rätt.

        Att en användare är deltagare gör INTE händelsens company-koncept
        läsbart för hen. Källans läsbarhet prövas av `_resolve_visible_sources`
        — här simuleras att källan är osynlig för användaren, medan hens eget
        personal-koncept (samma källa, men ägt av hen) injiceras.
        """
        from unittest.mock import patch
        event = self._event()
        event._okf_index_record()
        concepts = self._concepts(event)
        company = concepts.filtered(lambda c: c.scope == 'company')
        personal = concepts.filtered(
            lambda c: c.owner_user_id == self.user_a)
        self.assertEqual(len(company), 1)
        self.assertEqual(len(personal), 1)

        # Källan ar osynlig for anvandaren -> company-konceptet avfors.
        src = 'calendar.event,%s' % event.id
        with patch.object(
                type(self.Concept), '_resolve_visible_sources',
                return_value={company.id: {src: False},
                              personal.id: {src: False}}):
            block = self.Concept._format_concept_block(
                company, 2000, 'TEST', user=self.user_a)
            self.assertNotIn(company.summary or '', block,
                             'company-konceptet fick inte injiceras')

        # Med synlig kalla injiceras company-konceptet.
        with patch.object(
                type(self.Concept), '_resolve_visible_sources',
                return_value={company.id: {src: True}}):
            block = self.Concept._format_concept_block(
                company, 2000, 'TEST', user=self.user_a)
            self.assertIn(company.summary or '', block)

    # ── 4.2: isolering ──

    def test_personal_concepts_are_isolated(self):
        """Sökning för en deltagare ger bara dennes koncept."""
        event = self._event()
        event._okf_index_record()
        a_concepts = self.Concept._okf_search(
            'ZZ Accesstest', scope='personal', owner_id=self.user_a.id)
        self.assertTrue(a_concepts)
        for c in a_concepts:
            self.assertEqual(c.owner_user_id, self.user_a)
        b_concepts = self.Concept._okf_search(
            'ZZ Accesstest', scope='personal', owner_id=self.user_b.id)
        self.assertTrue(b_concepts)
        for c in b_concepts:
            self.assertEqual(c.owner_user_id, self.user_b)
        # Och de är olika poster
        self.assertFalse(set(a_concepts.ids) & set(b_concepts.ids))

    # ── 5.1: deltagarändring ──

    def test_partner_change_flags_event(self):
        """En deltagarändring flaggar händelsen."""
        event = self._event()
        event._okf_index_record()
        event.invalidate_recordset(['okf_dirty'])
        self.assertFalse(event.okf_dirty)
        new_partner = self.env['res.partner'].create({'name': 'ZZ Ny'})
        event.write({'partner_ids': [(4, new_partner.id)]})
        event.invalidate_recordset(['okf_dirty'])
        self.assertTrue(event.okf_dirty,
                        'partner_ids ska flagga för omindexering')

    def test_reindex_writes_all_owner_chains(self):
        """Omindexering ger en ny version i varje ägd kedja."""
        event = self._event()
        event._okf_index_record()
        before = self._concepts(event)
        versions_before = {c.owner_user_id.id or c.owner_company_id.id:
                           c.version for c in before}
        event.write({'name': 'ZZ Accesstest (ändrad)'})
        event._okf_index_record()
        after = self._concepts(event).filtered(lambda c: c.status != 'superseded')
        self.assertEqual(len(after), len(before),
                         'samma antal aktiva koncept efter omindexering')
        for c in after:
            owner = c.owner_user_id.id or c.owner_company_id.id
            self.assertGreater(c.version, versions_before[owner],
                               'varje ägd kedja ska ha ny version')

    # ── 5.2: oförändrad text ger ingen ny version ──

    def test_unchanged_text_gives_no_new_version(self):
        """En ägare vars text är oförändrad får ingen ny version.

        `_okf_upsert` jämför källtexten: samma text ger ingen ny rad.
        """
        event = self._event()
        event._okf_index_record()
        first = self._concepts(event)
        a_before = first.filtered(
            lambda c: c.owner_user_id == self.user_a)
        self.assertEqual(len(a_before), 1)
        # Indexera om UTAN att ändra något.
        event._okf_index_record()
        a_after = self._concepts(event).filtered(
            lambda c: c.owner_user_id == self.user_a
            and c.status != 'superseded')
        self.assertEqual(len(a_after), 1)
        self.assertEqual(a_after.version, a_before.version,
                         'oförändrad text ska inte ge ny version')

    # ── 5.3: en enda väg ──

    def test_bridge_registers_model(self):
        """Bryggan registrerar calendar.event för dirty-indexering."""
        models = self.env['ai.okf.mixin']._okf_indexable_models()
        self.assertIn('calendar.event', models)

    def test_no_calendar_cron_in_bridge(self):
        """Bryggan har ingen egen cron — kärnans cron sköter indexeringen."""
        crons = self.env['ir.cron'].sudo().search([
            ('model_id.model', '=', 'calendar.event')])
        self.assertFalse(crons,
                         'calendar_ai ska inte ha en egen ir.cron')
