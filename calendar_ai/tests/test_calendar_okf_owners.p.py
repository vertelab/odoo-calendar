# -*- coding: utf-8 -*-
"""En händelse ger ett koncept per intressent (calendar-okf D1, D2, D4).

VARFÖR: bryggan lade händelser bara i FÖRETAGSMINNET
(`_okf_owner_vals` returnerar `owner_company_id`). En händelse är personlig
för den som är inbjuden: "vad har jag bokat i oktober" är en fråga om *mina*
möten. Samma händelse kan ha betydelse för båda — för deltagaren (personligt)
och för organisationen (delat).

Dessa tester bevisar:
  1. en händelse ger ett company-koncept + ett personal per deltagare
  2. externa deltagare (ingen user) ger inget personligt koncept
  3. två ägares koncept delar aldrig nyckel
  4. flaggan rensas en gång för alla ägare
  5. volymtaket begränsar och loggar
"""

import datetime
import logging

from odoo import fields
from odoo.tests import common, tagged


@tagged('calendar_ai', 'okf', 'post_install', '-at_install')
class TestCalendarOkfOwners(common.TransactionCase):
    """D1/D2/D4: ägarlistan och volymtaket."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Concept = cls.env['ai.okf.concept']
        cls.Event = cls.env['calendar.event']
        cls.company = cls.env.ref('base.main_company')
        cls.start = datetime.datetime(2026, 5, 4, 13, 0, 0)
        cls.stop = datetime.datetime(2026, 5, 4, 14, 0, 0)

        def _user(name, login):
            partner = cls.env['res.partner'].create({
                'name': name, 'email': '%s@example.com' % login})
            return cls.env['res.users'].create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'partner_id': partner.id})

        cls.user_a = _user('ZZ Cal A', 'zz_cal_a')
        cls.user_b = _user('ZZ Cal B', 'zz_cal_b')
        cls.user_c = _user('ZZ Cal C', 'zz_cal_c')
        # En extern kontakt: partner UTAN user.
        cls.external = cls.env['res.partner'].create({
            'name': 'ZZ Extern Konsult', 'email': 'extern@example.com'})

    def _event(self, partners, **kw):
        vals = {
            'name': 'ZZ Kalendertest',
            'start': fields.Datetime.to_string(self.start),
            'stop': fields.Datetime.to_string(self.stop),
            'partner_ids': [(6, 0, [p.id for p in partners])],
        }
        vals.update(kw)
        return self.Event.create(vals)

    def _concepts(self, event):
        return self.Concept.search([
            ('source_ref', '=', 'calendar.event,%s' % event.id)])

    # ── 2.0: bolagshärledningen ──

    def test_company_id_without_oca_module(self):
        """Bolaget härleds utan `company_id` (OCA-modulen saknas).

        `calendar.event` har inget `company_id` i Odoo 18 core. Utan
        prövningen kraschade `_okf_owner_vals()` med AttributeError.
        """
        event = self._event([self.user_a.partner_id])
        self.assertNotIn('company_id', event._fields,
                         'testet förutsätter att OCA-modulen inte är '
                         'installerad — annars prövas inte fallbacken')
        company = event._okf_company_id()
        self.assertTrue(company)
        # Organisatörens bolag (här env.company, samma i testet).
        self.assertEqual(company, event.user_id.company_id
                         or self.env.company)

    def test_owner_vals_uses_derived_company(self):
        """`_okf_owner_vals()` använder det härledda bolaget."""
        event = self._event([self.user_a.partner_id])
        vals = event._okf_owner_vals()
        self.assertEqual(vals['owner_company_id'],
                         event._okf_company_id().id)

    def test_company_id_fallback_without_organizer(self):
        """Utan organisatör faller bolaget tillbaka på env.company."""
        event = self._event([self.user_a.partner_id], user_id=False)
        self.assertFalse(event.user_id)
        self.assertEqual(event._okf_company_id(), self.env.company)

    # ── 2.1: deltagare -> användare ──

    def test_attendee_users_maps_partners(self):
        """En intern och en extern deltagare ger en användare."""
        event = self._event([self.user_a.partner_id, self.external])
        users = event._attendee_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users, self.user_a)

    def test_attendee_users_empty_without_partners(self):
        """En händelse utan deltagare ger inga användare."""
        event = self._event([])
        self.assertFalse(event._attendee_users())

    def test_attendee_users_excludes_inactive(self):
        """En inaktiverad användare är ingen deltagare."""
        self.user_c.active = False
        event = self._event([self.user_a.partner_id,
                             self.user_c.partner_id])
        self.assertEqual(event._attendee_users(), self.user_a)

    # ── 2.2: ägarlistan ──

    def test_owner_list_company_plus_attendees(self):
        """Tre interna deltagare ger fyra ägare."""
        event = self._event([self.user_a.partner_id,
                             self.user_b.partner_id,
                             self.user_c.partner_id])
        owners = event._okf_owner_vals_list()
        self.assertEqual(len(owners), 4)
        self.assertIn('owner_company_id', owners[0])
        uids = {o.get('owner_user_id') for o in owners[1:]}
        self.assertEqual(uids, {self.user_a.id, self.user_b.id,
                                self.user_c.id})

    def test_owner_list_company_only_without_attendees(self):
        """En händelse utan interna deltagare ger ett company-koncept."""
        event = self._event([self.external])
        owners = event._okf_owner_vals_list()
        self.assertEqual(len(owners), 1)
        self.assertIn('owner_company_id', owners[0])

    # ── 2.2 + 2.4: indexeringen ──

    def test_three_attendees_give_four_concepts(self):
        """En händelse med tre deltagare ger fyra koncept."""
        event = self._event([self.user_a.partner_id,
                             self.user_b.partner_id,
                             self.user_c.partner_id])
        event._okf_index_record()
        concepts = self._concepts(event)
        self.assertEqual(len(concepts), 4)
        scopes = concepts.mapped('scope')
        self.assertEqual(scopes.count('company'), 1)
        self.assertEqual(scopes.count('personal'), 3)

    def test_external_attendee_gives_no_personal_concept(self):
        """En extern deltagare får inget personligt koncept."""
        event = self._event([self.user_a.partner_id, self.external])
        event._okf_index_record()
        concepts = self._concepts(event)
        self.assertEqual(len(concepts), 2)
        personal = concepts.filtered(lambda c: c.scope == 'personal')
        self.assertEqual(len(personal), 1)
        self.assertEqual(personal.owner_user_id, self.user_a)

    def test_concept_keys_are_distinct_per_owner(self):
        """Två deltagares koncept delar aldrig nyckel."""
        event = self._event([self.user_a.partner_id, self.user_b.partner_id])
        event._okf_index_record()
        concepts = self._concepts(event)
        keys = concepts.mapped('concept_key')
        self.assertEqual(len(keys), len(set(keys)))
        for c in concepts:
            if c.scope == 'personal':
                self.assertIn('user.%s' % c.owner_user_id.id, c.concept_key)

    def test_dirty_cleared_once(self):
        """Flaggan rensas en gång efter samtliga ägare."""
        event = self._event([self.user_a.partner_id, self.user_b.partner_id])
        self.assertTrue(event.okf_dirty)
        event._okf_index_record()
        event.invalidate_recordset(['okf_dirty'])
        self.assertFalse(event.okf_dirty)

    # ── 2.3: volymtaket ──

    def test_owner_limit_default(self):
        """Taket är 25 utan konfiguration."""
        event = self._event([])
        self.assertEqual(event._okf_owner_limit(), 25)

    def test_owner_limit_is_configurable(self):
        """Taket kan sättas via systemparametern."""
        self.env['ir.config_parameter'].sudo().set_param(
            'calendar_ai.okf_owner_limit', '2')
        event = self._event([])
        self.assertEqual(event._okf_owner_limit(), 2)

    def test_owner_limit_invalid_value_falls_back(self):
        """Ett icke-numeriskt värde faller tillbaka på 25."""
        self.env['ir.config_parameter'].sudo().set_param(
            'calendar_ai.okf_owner_limit', 'inte-ett-tal')
        event = self._event([])
        self.assertEqual(event._okf_owner_limit(), 25)

    def test_owner_limit_caps_attendees_and_logs(self):
        """En händelse över taket begränsas och begränsningen loggas."""
        self.env['ir.config_parameter'].sudo().set_param(
            'calendar_ai.okf_owner_limit', '2')
        event = self._event([self.user_a.partner_id,
                             self.user_b.partner_id,
                             self.user_c.partner_id])
        logger = logging.getLogger(
            'odoo.addons.calendar_ai.models.calendar_event')
        with self.assertLogs(logger, level=logging.INFO) as cm:
            owners = event._okf_owner_vals_list()
        # Företaget + taket (2) = 3 ägare, inte 4.
        self.assertEqual(len(owners), 3)
        joined = '\n'.join(cm.output)
        self.assertIn('begränsar till 2', joined)

    def test_owner_limit_caps_concepts(self):
        """Taket begränsar antalet koncept."""
        self.env['ir.config_parameter'].sudo().set_param(
            'calendar_ai.okf_owner_limit', '1')
        event = self._event([self.user_a.partner_id,
                             self.user_b.partner_id,
                             self.user_c.partner_id])
        event._okf_index_record()
        concepts = self._concepts(event)
        # Företaget + 1 deltagare.
        self.assertEqual(len(concepts), 2)
