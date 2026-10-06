# -*- coding: utf-8 -*-
# Part of calendar_ics_invitations. See LICENSE file for full copyright and licensing details.

import base64
import datetime
from unittest.mock import patch

import vobject
from odoo import fields
from odoo.tests import common


class TestIcsIntegration(common.TransactionCase):
    """Assert the mail flow, cancellation and response distribution
    (tasks 4.x, 5.x, 8.x)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizer_partner = cls.env['res.partner'].create({
            'name': 'Organizer', 'email': 'organizer@example.com'})
        cls.organizer_user = cls.env['res.users'].create({
            'name': 'Organizer', 'login': 'organizer',
            'email': 'organizer@example.com',
            'partner_id': cls.organizer_partner.id})
        cls.attendee_1 = cls.env['res.partner'].create({
            'name': 'Kalle', 'email': 'kalle@example.com'})
        cls.attendee_2 = cls.env['res.partner'].create({
            'name': 'Nisse', 'email': 'nisse@example.com'})
        cls.start = datetime.datetime(2026, 5, 4, 13, 0, 0)
        cls.stop = datetime.datetime(2026, 5, 4, 14, 0, 0)

    def _event(self, **kwargs):
        values = {
            'name': 'Review',
            'start': fields.Datetime.to_string(self.start),
            'stop': fields.Datetime.to_string(self.stop),
            'user_id': self.organizer_user.id,
            'partner_ids': [(6, 0, [self.attendee_1.id, self.attendee_2.id])],
        }
        values.update(kwargs)
        return self.env['calendar.event'].create(values)

    def _ics_attachments(self, mails):
        result = []
        for mail in mails:
            for attachment in mail.attachment_ids:
                if attachment.mimetype == 'text/calendar':
                    raw = base64.b64decode(attachment.datas)
                    result.append(vobject.readOne(raw.decode('utf-8')))
        return result

    # --- 4.x cancellation -------------------------------------------------

    def test_cancellation_payload(self):
        event = self._event()
        event._ensure_ics_uid()
        uid = event.ics_uid
        event.write({'name': 'Review v2'})
        last_sequence = event.ics_sequence
        # The cancellation path bumps the sequence before building the payload.
        event.with_context(skip_ics_bump=True).write(
            {'ics_sequence': event.ics_sequence + 1})
        cal = vobject.readOne(
            event._get_ics_file(method='CANCEL')[event.id].decode('utf-8'))
        self.assertEqual(cal.method.value, 'CANCEL')
        self.assertEqual(cal.vevent.status.value, 'CANCELLED')
        self.assertEqual(cal.vevent.uid.value, uid)
        self.assertGreater(int(cal.vevent.sequence.value), last_sequence)

    def test_unlink_sends_cancel_attachment(self):
        event = self._event()
        event._ensure_ics_uid()
        uid = event.ics_uid
        attendee_ids = event.attendee_ids.ids
        event.unlink()
        mails = self.env['mail.mail'].search([
            ('model', '=', 'calendar.attendee'),
            ('res_id', 'in', attendee_ids),
        ])
        self.assertTrue(mails)
        cancels = [cal for cal in self._ics_attachments(mails)
                   if cal.method.value == 'CANCEL']
        self.assertTrue(cancels, "No METHOD:CANCEL attachment found")
        self.assertEqual(cancels[0].vevent.uid.value, uid)

    # --- 5.x core mail flow ----------------------------------------------

    def test_send_mail_to_attendees_uses_override(self):
        event = self._event()
        event._ensure_ics_uid()
        template = self.env.ref('calendar.calendar_template_meeting_invitation')
        event.attendee_ids._send_mail_to_attendees(template, force_send=True)
        # message_notify attaches the ICS as an ir.attachment named
        # invitation.ics; one per recipient.
        attachments = self.env['ir.attachment'].search([
            ('name', '=', 'invitation.ics'),
            ('mimetype', '=', 'text/calendar'),
        ])
        self.assertTrue(attachments)
        requests = []
        for attachment in attachments:
            raw = base64.b64decode(attachment.datas)
            cal = vobject.readOne(raw.decode('utf-8'))
            if cal.method.value == 'REQUEST':
                requests.append(cal)
        self.assertTrue(requests, "No METHOD:REQUEST attachment found")
        self.assertNotIn(' ', requests[0].vevent.uid.value)

    def test_override_is_invoked_through_send_mail(self):
        """Guard against a core signature change: the override must still be
        reached through _send_mail_to_attendees()."""
        event = self._event()
        event._ensure_ics_uid()
        original = type(event)._get_ics_file
        calls = []

        def spy(self, *args, **kwargs):
            calls.append(args)
            return original(self, *args, **kwargs)

        template = self.env.ref('calendar.calendar_template_meeting_invitation')
        with patch.object(type(event), '_get_ics_file', spy):
            event.attendee_ids._send_mail_to_attendees(template, force_send=True)
        self.assertTrue(calls, "_get_ics_file was not called by the core flow")

    def test_alarm_path_payload(self):
        event = self._event()
        event._ensure_ics_uid()
        cal = vobject.readOne(event._get_ics_file()[event.id].decode('utf-8'))
        self.assertEqual(cal.method.value, 'REQUEST')

    # --- 8.x response distribution ---------------------------------------

    def test_response_distributed_to_other_attendees(self):
        event = self._event()
        event._ensure_ics_uid()
        responder = event.attendee_ids.filtered(
            lambda a: a.partner_id == self.attendee_1)
        nisse = event.attendee_ids.filtered(
            lambda a: a.partner_id == self.attendee_2)
        responder.do_accept()
        mails = self.env['mail.mail'].search([
            ('model', '=', 'calendar.attendee'),
            ('res_id', '=', nisse.id),
        ])
        self.assertTrue(mails, "Nisse received no response update")
        # The responder and the organizer are not notified.
        self.assertFalse(self.env['mail.mail'].search([
            ('model', '=', 'calendar.attendee'),
            ('res_id', '=', responder.id)]))
        self.assertFalse(self.env['mail.mail'].search([
            ('model', '=', 'calendar.attendee'),
            ('res_id', 'in', event.attendee_ids.filtered(
                lambda a: a.partner_id == self.organizer_partner).ids)]))

    def test_response_payload_carries_partstat_and_sequence(self):
        event = self._event()
        event._ensure_ics_uid()
        responder = event.attendee_ids.filtered(
            lambda a: a.partner_id == self.attendee_1)
        sequence_before = event.ics_sequence
        responder.do_accept()
        self.assertGreater(event.ics_sequence, sequence_before)
        cal = vobject.readOne(
            event._get_ics_file(method='REQUEST')[event.id].decode('utf-8'))
        self.assertEqual(cal.method.value, 'REQUEST')
        self.assertGreater(int(cal.vevent.sequence.value), sequence_before)
        partstat = {
            line.value: line.params['PARTSTAT'][0]
            for line in cal.vevent.contents.get('attendee', [])
        }
        self.assertEqual(partstat['mailto:kalle@example.com'], 'ACCEPTED')

    def test_no_response_update_on_non_state_write(self):
        event = self._event()
        event._ensure_ics_uid()
        before = self.env['mail.mail'].search_count([])
        event.attendee_ids.write({'email': 'kalle@example.com'})
        after = self.env['mail.mail'].search_count([])
        self.assertEqual(after, before)

    def test_system_state_reset_not_distributed(self):
        """Core resets attendee state to needsAction on a time change; that
        must not be distributed as a response."""
        event = self._event()
        event._ensure_ics_uid()
        attendee = event.attendee_ids[0]
        before = self.env['mail.mail'].search_count([])
        attendee.with_context(skip_response_update=True).write(
            {'state': 'needsAction'})
        after = self.env['mail.mail'].search_count([])
        self.assertEqual(after, before)

    def test_ensure_uid_does_not_bump_sequence_in_payload_loop(self):
        event_1 = self._event()
        event_2 = self._event(name='Second')
        before = {event_1.id: event_1.ics_sequence,
                  event_2.id: event_2.ics_sequence}
        (event_1 | event_2)._get_ics_file()
        for event in (event_1 | event_2):
            self.assertEqual(event.ics_sequence, before[event.id])
