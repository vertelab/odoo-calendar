# -*- coding: utf-8 -*-
"""calendar.event — OKF-indexerbar (calendar_ai).

Modellen äger sina KÄLLOR; `ai.okf.mixin` äger fälten och flaggan.

En händelse är tidsbunden: namn, datum och deltagare är det en användare
söker ("vad har vi bokat i oktober"). Modellen sammanfattar sig SJÄLV —
en LLM hade formulerat om samma fakta olika varje gång, och datumet är
det viktigaste ordet.
"""

from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _name = 'calendar.event'
    _inherit = ['calendar.event', 'ai.okf.mixin']

    # OKF-taggar: egen relationstabell (en many2many kan inte
    # ligga pa en abstrakt mixin — den ger samma tabell for alla).
    okf_tags = fields.Many2many(
        'ai.okf.tag', 'calendar_event_okf_tag_rel', 'res_id', 'tag_id',
        string='OKF Tags')

    # ── Källor ─────────────────────────────────────────────────────────
    #
    # `okf_body` och `okf_links` är GENERISKA i mixinen:
    #   okf_body  = alla HTML/Text-fält + name
    #   okf_links = relationsfält där målet bär mixinen
    #               → partner_ids blir länkar när base_ai finns
    #
    # Bryggan skriver det som är specifikt för kalendern.

    def _okf_summary_source(self, owner_vals=None):
        """Händelsens EGEN sammanfattning: namn, datum, plats.

        Detta är vad en användare söker, och det är deterministiskt —
        samma händelse ger samma text.

        `owner_vals` (D3): ägaren konceptet byggs för. När ägaren är en
        ANVÄNDARE kapas deltagarlistan — Björns namn ska inte hamna i Annas
        personliga minne (och en extern deltagares namn inte alls). När
        ägaren är FÖRETAGET behålls listan: det konceptet är delat mellan
        dem som har rätt till det och får namnge dem.

        Utan argument (en äldre kärna) behålls listan — det ofarliga fallet,
        ingen krasch.
        """
        self.ensure_one()
        bits = [self.name or '']
        if self.start:
            bits.append('Start: %s' % self.start.strftime('%Y-%m-%d %H:%M'))
        if self.stop and self.stop != self.start:
            bits.append('Slut: %s' % self.stop.strftime('%Y-%m-%d %H:%M'))
        if self.location:
            bits.append('Plats: %s' % self.location)
        if self.partner_ids and not self._okf_is_personal_owner(owner_vals):
            names = self.partner_ids.mapped('name')[:5]
            bits.append('Deltagare: %s' % ', '.join(n for n in names if n))
        return ' — '.join(b for b in bits if b) or None

    def _okf_is_personal_owner(self, owner_vals):
        """Är konceptet personligt (ägt av en användare)?

        `owner_vals` är `_okf_owner_vals_list()`:s dict: antingen
        `{'owner_company_id': ...}` eller `{'owner_user_id': ...}`.
        `None` (ingen ägarkontext, t.ex. en äldre kärna) räknas som INTE
        personligt — då visas deltagarlistan, vilket är det ofarliga fallet.
        """
        return bool((owner_vals or {}).get('owner_user_id'))

    def _okf_artifact_type(self):
        """Bryggans egen typ (okf-mixin D12).

        Heter 'calendar_event', inte 'event': `website_ai_event` äger
        redan 'event' för `event.event`. Två bryggor kan inte dela namn —
        `ai.artifact.type` har UNIQUE(name), och taxonomin ska kunna
        spåras till EN brygga.
        """
        return 'calendar_event'

    def _okf_dirty_fields(self):
        """Fält vars ändring gör OKF-fälten inaktuella.

        Bara innehåll och tid. `alarm_ids`, `attendee_ids` och räknare
        ändras ofta och säger inget om texten.
        """
        return {'name', 'description', 'start', 'stop', 'location',
                'partner_ids', 'categ_ids', 'active'}

    def _okf_skip_reason(self):
        """Arkiverad händelse = "tomt just nu", inte "tomt för alltid"."""
        return None

    def _okf_company_id(self):
        """Händelsens bolag.

        `calendar.event` har INGET `company_id` i Odoo 18 core — kalendern
        är inte multi-company i CE. Fältet kommer från OCA:s
        `calendar_event_multi_company`, som kan vara installerad eller inte.

        Därför tre steg (calendar-event-okf-personal-company D1):

          1. `company_id` om fältet FINNS och är satt — då är det
             auktoritativt (OCA-modulen är installerad).
          2. organisatörens bolag (`user_id.company_id`) — händelsen
             tillhör den som bokade den.
          3. `env.company` — sista utväg när organisatören saknas.

        FYND 2026-10-07: den ursprungliga `_okf_owner_vals()` läste
        `self.company_id` rakt av. Det kraschade med AttributeError så fort
        modulen kördes i en databas utan OCA-modulen — vilket aldrig
        upptäcktes eftersom `calendar_ai` aldrig installerats.
        """
        self.ensure_one()
        if 'company_id' in self._fields and self.company_id:
            return self.company_id
        return self.user_id.company_id or self.env.company

    def _okf_owner_vals(self):
        """Händelsens företag — se `_okf_company_id()`."""
        self.ensure_one()
        return {'owner_company_id': self._okf_company_id().id}

    # ── Ägare: företaget + en per deltagare (D1, D2) ───────────────────

    def _attendee_users(self):
        """Deltagare som är användare (`res.users`).

        `partner_ids` är `res.partner`; en partner har 0 eller 1 user.
        Externa deltagare (ingen user) faller bort — de har ingen
        användare att äga ett personligt koncept, och ska inte ha ett.

        Returnerar ett recordset (unikt per användare, ordnat på id) så
        anroparen får en deterministisk ordning.
        """
        self.ensure_one()
        partners = self.partner_ids
        if not partners:
            return self.env['res.users'].browse()
        users = self.env['res.users'].sudo().search(
            [('partner_id', 'in', partners.ids)], order='id')
        # Företagets egna resurs-/systemanvändare är inte deltagare i
        # mänsklig mening — men de kan vara det, så vi filtrerar bara på
        # `active` och låter `share` vara (en portal-användare är en
        # person). Inaktiva användare hoppas över: de kan inte läsa något.
        return users.filtered('active')

    def _okf_owner_limit(self):
        """Tak för antal ägare (och därmed koncept) per händelse (D4).

        Konfigurerbar via systemparametern `calendar_ai.okf_owner_limit`,
        default 25. Skälet till ett tak: `_okf_dirty_fields()` innehåller
        `partner_ids`, så en deltagarändring skriver om SAMTLIGA ägares
        koncept. En händelse med 200 deltagare ger 201 koncept och 201
        skrivningar per ändring.

        Taket räknas på antalet ägare UTÖVER företaget — företaget är
        alltid med (det är händelsens organisatoriska koncept).
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'calendar_ai.okf_owner_limit', '25')
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            _logger.warning(
                'calendar_ai: okf_owner_limit är inte ett tal (%r) — '
                'använder 25', raw)
            limit = 25
        return limit if limit > 0 else 25

    def _okf_owner_vals_list(self):
        """Företaget + en ägare per deltagare som är en användare (D1).

        `_okf_index_record()` skriver ett koncept per ägare och sätter
        ägarläget i `concept_key` automatiskt — bryggan behöver inte röra
        `_okf_concept_key`.

        Företaget är alltid först (det konceptet finns även när alla
        deltagare är externa). Deltagarna begränsas av `_okf_owner_limit()`,
        och en begränsning loggas så den syns (D4).
        """
        self.ensure_one()
        owners = [self._okf_owner_vals()]
        users = self._attendee_users()
        limit = self._okf_owner_limit()
        if len(users) > limit:
            _logger.info(
                'calendar_ai: händelse %s har %d deltagar-användare — '
                'begränsar till %d (calendar_ai.okf_owner_limit)',
                self.id, len(users), limit)
            users = users[:limit]
        owners.extend({'owner_user_id': u.id} for u in users)
        return owners

    # ── Registrering (okf-mixin D11) ───────────────────────────────────

    def _register_hook(self):
        """Registrera händelsen för dirty-indexering.

        Registrering, inte överridning: `_okf_indexable_models()` är
        `@api.model` på en abstrakt modell (mätt på luke18 2026-09-22).
        """
        res = super()._register_hook()
        self.env['ai.okf.mixin']._okf_register_indexable('calendar.event')
        return res
