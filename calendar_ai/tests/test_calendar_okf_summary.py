# -*- coding: utf-8 -*-
"""Deltagarlistan kapas i personliga koncept (calendar-okf D3).

VARFÖR: Björns namn i Annas personliga minne är inte ett rättighetsläckage
(de var båda på mötet), men det är ett integritetsval. Det personliga minnet
är *Annas*; att lista andra där är att blanda in dem utan att de äger raden.
Och en extern deltagares namn skulle hamna i Annas minne.

Dessa tester bevisar:
  1. det personliga konceptet namnger inte de andra deltagarna
  2. company-konceptet får namnge dem (det är delat)
  3. namn, tid och plats finns i båda fallen
  4. anrop utan owner_vals (äldre kärna) kraschar inte
"""

import datetime

from odoo import fields
from odoo.tests import common, tagged


@tagged('calendar_ai', 'okf', 'post_install', '-at_install')
class TestCalendarOkfSummary(common.TransactionCase):
    """D3: sammanfattningen per ägare."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

        cls.user_a = _user('Anna Andersson', 'zz_sum_a')
        cls.user_b = _user('Björn Berg', 'zz_sum_b')

    def _event(self, **kw):
        vals = {
            'name': 'ZZ Sammanfattningstest',
            'start': fields.Datetime.to_string(self.start),
            'stop': fields.Datetime.to_string(self.stop),
            'location': 'Rum 3',
            'partner_ids': [(6, 0, [self.user_a.partner_id.id,
                                    self.user_b.partner_id.id])],
        }
        vals.update(kw)
        return self.Event.create(vals)

    def test_personal_summary_omits_attendees(self):
        """Det personliga konceptet namnger inte de andra deltagarna."""
        event = self._event()
        text = event._okf_summary_source(
            owner_vals={'owner_user_id': self.user_a.id})
        self.assertIn('ZZ Sammanfattningstest', text)
        self.assertNotIn('Björn Berg', text)
        self.assertNotIn('Anna Andersson', text)
        self.assertNotIn('Deltagare:', text)

    def test_company_summary_names_attendees(self):
        """Company-konceptet får namnge deltagarna."""
        event = self._event()
        text = event._okf_summary_source(
            owner_vals={'owner_company_id': self.env.company.id})
        self.assertIn('Deltagare:', text)
        self.assertIn('Anna Andersson', text)
        self.assertIn('Björn Berg', text)

    def test_summary_keeps_name_time_location(self):
        """Namn, start och plats finns i båda fallen."""
        event = self._event()
        for owner in ({'owner_company_id': self.env.company.id},
                      {'owner_user_id': self.user_a.id}):
            text = event._okf_summary_source(owner_vals=owner)
            self.assertIn('ZZ Sammanfattningstest', text)
            self.assertIn('Start: 2026-05-04 13:00', text)
            self.assertIn('Plats: Rum 3', text)

    def test_summary_without_owner_vals_does_not_crash(self):
        """Anrop utan argument (äldre kärna) ger en sammanfattning."""
        event = self._event()
        text = event._okf_summary_source()
        self.assertIn('ZZ Sammanfattningstest', text)
        # Utan ägarkontext visas deltagarlistan — det ofarliga fallet.
        self.assertIn('Deltagare:', text)

    def test_personal_summary_omits_external_attendee(self):
        """En extern deltagares namn hamnar inte i ett personligt koncept."""
        external = self.env['res.partner'].create({
            'name': 'ZZ Extern Person', 'email': 'extern2@example.com'})
        event = self._event(partner_ids=[(6, 0, [
            self.user_a.partner_id.id, external.id])])
        text = event._okf_summary_source(
            owner_vals={'owner_user_id': self.user_a.id})
        self.assertNotIn('ZZ Extern Person', text)

    def test_indexed_personal_concepts_omit_attendees(self):
        """Ände-till-ände: de indexerade personliga koncepten är kapade."""
        event = self._event()
        event._okf_index_record()
        concepts = self.env['ai.okf.concept'].search([
            ('source_ref', '=', 'calendar.event,%s' % event.id)])
        personal = concepts.filtered(lambda c: c.scope == 'personal')
        self.assertTrue(personal)
        for c in personal:
            self.assertNotIn('Deltagare:', c.summary)
        company = concepts.filtered(lambda c: c.scope == 'company')
        self.assertIn('Deltagare:', company.summary)
