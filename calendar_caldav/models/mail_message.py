"""iMIP — invitations that arrive as a mail attachment (RFC 6047).

Outlook and Google do not speak CalDAV; they mail an ``invitation.ics``.
Without this, those users can never be reached, which is the whole point
of the feature.

The dangerous part is that an ``.ics`` is a write instruction against
someone's calendar, and anyone can mail one claiming any ``ORGANIZER``.
So a message is only applied when we can tie the payload to the sender:

* the ``ORGANIZER`` address must belong to the envelope sender, and
* the sender domain must publish SPF/DKIM/DMARC, and
* the recipient must be an Odoo user we can identify.

Anything else is recorded on the message instead of written to a
calendar — visible, but inert.
"""

import logging

from odoo import models

from ..services.ical import (
    PARTSTAT_TO_STATE,
    SUPPORTED_METHODS,
    ItipError,
    parse_itip,
)

_logger = logging.getLogger(__name__)

#: Header Odoo's mail gateway sets with the authenticated sender domain.
AUTH_HEADERS = (
    'Authentication-Results',
    'Received-SPF',
    'DKIM-Signature',
)


class MailMessage(models.Model):
    _inherit = 'mail.message'

    # ── entry point ─────────────────────────────────────────────────
    def message_parse(self, message, save_original=False):
        """Pick up an ``.ics`` attachment before the message is stored.

        ``message_parse`` is where every inbound mail passes, so it is the
        only place that sees an invitation regardless of which alias,
        gateway or route delivered it.
        """
        result = super().message_parse(message, save_original=save_original)
        try:
            self._process_itip_attachments(message, result)
        except Exception as exc:  # never break mail delivery over this
            _logger.warning('[iMIP] could not process invitation: %s', exc)
        return result

    # ── internals ───────────────────────────────────────────────────
    def _process_itip_attachments(self, message, parsed):
        """Find ``text/calendar`` parts and act on the ones we trust."""
        for part in message.walk():
            if part.get_content_type() != 'text/calendar':
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            self._handle_itip_payload(payload, message, parsed)

    def _handle_itip_payload(self, payload, message, parsed):
        try:
            itip = parse_itip(payload)
        except ItipError as exc:
            _logger.info('[iMIP] attachment is not usable iTIP: %s', exc)
            return False

        if itip['method'] not in SUPPORTED_METHODS:
            _logger.info('[iMIP] unsupported method %r', itip['method'])
            return False

        sender = (parsed.get('email_from') or '').strip().lower()
        organizer = (itip['organizer'] or {}).get('email', '').lower()

        if not self._sender_may_speak_for(sender, organizer, message):
            _logger.info(
                '[iMIP] refusing %s from %s: organiser is %s',
                itip['method'], sender or '<none>', organizer or '<none>')
            # Silence is the worst outcome: a customer with a broken SPF
            # record would never learn that their invitations are being
            # dropped. Say so where the user will actually see it.
            self._report_rejected_itip(itip, parsed, sender, organizer)
            return False

        recipient = self._recipient_user(parsed)
        if not recipient:
            _logger.info('[iMIP] no Odoo user among the recipients')
            return False

        return self._apply_itip(itip, recipient)

    def _report_rejected_itip(self, itip, parsed, sender, organizer):
        """Post a note on the message explaining why nothing happened.

        The invitation is *not* applied. This only makes the refusal
        visible, so a misconfigured sender domain is diagnosable instead
        of invisible.
        """
        reason = self._rejection_reason(sender, organizer, parsed)
        summary = itip['event'].get('name') or '(no summary)'
        body = (
            '<p><strong>En mötesinbjudan togs inte emot.</strong></p>'
            '<p>Bilagan <code>.ics</code> kunde inte verifieras som '
            'kommande från arrangören, så ingen händelse skapades i '
            'kalendern.</p>'
            '<ul>'
            '<li>Händelse: %s</li>'
            '<li>Arrangör i bilagan: %s</li>'
            '<li>Faktisk avsändare: %s</li>'
            '<li>Orsak: %s</li>'
            '</ul>'
            '<p>Om avsändaren är seriös beror det oftast på att domänens '
            'SPF/DKIM-post saknas eller är felaktig.</p>'
        ) % (
            summary,
            organizer or '(saknas)',
            sender or '(saknas)',
            reason,
        )
        try:
            self.sudo().message_post(
                body=body,
                subtype_xmlid='mail.mt_note',
                message_type='notification',
            )
        except Exception as exc:  # reporting must never break mail delivery
            _logger.warning('[iMIP] could not post rejection note: %s', exc)

    def _rejection_reason(self, sender, organizer, parsed):
        """Name the specific check that failed, so the note is actionable."""
        if not sender:
            return 'mejlet har ingen avsändaradress'
        if not organizer:
            return 'bilagan saknar ORGANIZER'
        if sender != organizer:
            return 'ORGANIZER i bilagan stämmer inte med avsändaren'
        return 'avsändardomänen kunde inte verifieras (SPF/DKIM/DMARC)' 

    def _sender_may_speak_for(self, sender, organizer, message):
        """Only the organiser may send a REQUEST or CANCEL for their event."""
        if not sender or not organizer:
            return False
        if sender != organizer:
            return False
        return self._domain_is_authenticated(sender, message)

    def _domain_is_authenticated(self, sender, message):
        """Require a passing authentication result for the sender domain.

        A missing header is not a pass: an attacker controls their own
        mail server and simply will not add one.
        """
        domain = sender.rsplit('@', 1)[-1]
        for header in AUTH_HEADERS:
            value = (message.get(header) or '').lower()
            if not value:
                continue
            if domain not in value:
                continue
            if 'pass' in value and 'fail' not in value:
                return True
        _logger.info('[iMIP] no passing authentication for %s', domain)
        return False

    def _recipient_user(self, parsed):
        """The Odoo user this invitation was addressed to."""
        candidates = []
        for key in ('to', 'cc', 'delivered-to', 'email_to'):
            value = parsed.get(key) or ''
            candidates.extend(
                part.strip().strip('<>') for part in value.split(',') if part)
        emails = [c for c in candidates if '@' in c]
        if not emails:
            return False
        return self.env['res.users'].sudo().search(
            [('partner_id.email', 'in', emails)], limit=1)

    def _apply_itip(self, itip, user):
        """Write the invitation into the recipient's calendar."""
        Event = self.env['calendar.event'].sudo().with_user(user)
        uid = itip['uid']
        existing = Event.search([('uuid', '=', uid)], limit=1)

        if itip['method'] == 'CANCEL':
            if existing and itip['sequence'] >= (existing.itip_sequence or 0):
                existing.unlink()
                return True
            return False

        if itip['method'] == 'REPLY':
            # A REPLY from an external organiser concerns an event we
            # organise; update the attendee row it names.
            if not existing:
                return False
            for line in itip['attendees']:
                state = PARTSTAT_TO_STATE.get(line['partstat'])
                if not state:
                    continue
                rows = existing.attendee_ids.filtered(
                    lambda a, e=line['email']: (a.email or '') == e)
                rows.write({'state': state})
            return True

        if existing and itip['sequence'] < (existing.itip_sequence or 0):
            return False

        values = dict(itip['event'])
        values.update({
            'uuid': uid,
            'itip_sequence': itip['sequence'],
            'imip_organizer': (itip['organizer'] or {}).get('email') or False,
        })
        # The recipient is a participant, otherwise the event is invisible
        # to them in Odoo's own calendar views.
        values['partner_ids'] = [(4, user.partner_id.id)]

        if existing:
            existing.write(values)
            event = existing
        else:
            event = Event.create(values)

        self._sync_attendees(event, itip['attendees'])
        _logger.info('[iMIP] %s applied for user %s (event %s)',
                     itip['method'], user.login, event.id)
        return True

    def _sync_attendees(self, event, attendees):
        Attendee = self.env['calendar.attendee'].sudo()
        Partner = self.env['res.partner'].sudo()
        for line in attendees:
            email = line['email']
            partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': line['name'] or email,
                    'email': email,
                })
            state = PARTSTAT_TO_STATE.get(line['partstat'], 'needsAction')
            row = Attendee.search([
                ('event_id', '=', event.id),
                ('partner_id', '=', partner.id),
            ], limit=1)
            if row:
                row.write({'state': state})
            else:
                Attendee.create({
                    'event_id': event.id,
                    'partner_id': partner.id,
                    'email': email,
                    'common_name': line['name'] or partner.name,
                    'state': state,
                })
