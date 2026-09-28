# -*- coding: utf-8 -*-
"""calendar.event — OKF-indexerbar (calendar_ai).

Modellen äger sina KÄLLOR; `ai.okf.mixin` äger fälten och flaggan.

En händelse är tidsbunden: namn, datum och deltagare är det en användare
söker ("vad har vi bokat i oktober"). Modellen sammanfattar sig SJÄLV —
en LLM hade formulerat om samma fakta olika varje gång, och datumet är
det viktigaste ordet.
"""

from odoo import models, fields


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

    def _okf_summary_source(self):
        """Händelsens EGEN sammanfattning: namn, datum, plats.

        Detta är vad en användare söker, och det är deterministiskt —
        samma händelse ger samma text.
        """
        self.ensure_one()
        bits = [self.name or '']
        if self.start:
            bits.append('Start: %s' % self.start.strftime('%Y-%m-%d %H:%M'))
        if self.stop and self.stop != self.start:
            bits.append('Slut: %s' % self.stop.strftime('%Y-%m-%d %H:%M'))
        if self.location:
            bits.append('Plats: %s' % self.location)
        if self.partner_ids:
            names = self.partner_ids.mapped('name')[:5]
            bits.append('Deltagare: %s' % ', '.join(n for n in names if n))
        return ' — '.join(b for b in bits if b) or None

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

    def _okf_owner_vals(self):
        """Händelsens företag — inte `env.company` (multi-company)."""
        self.ensure_one()
        return {'owner_company_id': (self.company_id or self.env.company).id}

    # ── Registrering (okf-mixin D11) ───────────────────────────────────

    def _register_hook(self):
        """Registrera händelsen för dirty-indexering.

        Registrering, inte överridning: `_okf_indexable_models()` är
        `@api.model` på en abstrakt modell (mätt på luke18 2026-09-22).
        """
        res = super()._register_hook()
        self.env['ai.okf.mixin']._okf_register_indexable('calendar.event')
        return res
