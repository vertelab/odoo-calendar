# -*- coding: utf-8 -*-
# Part of calendar_ics_invitations. See LICENSE file for full copyright and licensing details.

import datetime

from odoo import fields
from odoo.tests import common


class TestIcsState(common.TransactionCase):
    """Assert the persisted payload state (task 2.x)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Kalle Kula', 'email': 'kalle@example.com'})
        cls.start = datetime.datetime(2026, 4, 1, 9, 0, 0)
        cls.stop = datetime.datetime(2026, 4, 1, 10, 0, 0)

    def _event(self, **kwargs):
        values = {
            'name': 'Sync',
            'start': fields.Datetime.to_string(self.start),
            'stop': fields.Datetime.to_string(self.stop),
            'partner_ids': [(6, 0, [self.partner.id])],
        }
        values.update(kwargs)
        return self.env['calendar.event'].create(values)

    def test_ensure_ics_uid_generates_and_persists(self):
        event = self._event()
        self.assertFalse(event.ics_uid)
        uid = event._ensure_ics_uid()
        self.assertTrue(uid)
        self.assertNotIn(' ', uid)
        self.assertEqual(event.ics_uid, uid)
        # Second call returns the identical value.
        self.assertEqual(event._ensure_ics_uid(), uid)

    def test_uid_persistence_does_not_bump_sequence(self):
        event = self._event()
        before = event.ics_sequence
        event._ensure_ics_uid()
        self.assertEqual(event.ics_sequence, before)

    def test_write_bumps_sequence_on_scheduling_field(self):
        event = self._event()
        before = event.ics_sequence
        event.write({'name': 'Sync renamed'})
        self.assertEqual(event.ics_sequence, before + 1)

    def test_write_does_not_bump_on_unrelated_field(self):
        event = self._event()
        before = event.ics_sequence
        event.write({'active': True})
        self.assertEqual(event.ics_sequence, before)

    def test_skip_ics_bump_context(self):
        event = self._event()
        before = event.ics_sequence
        event.with_context(skip_ics_bump=True).write({'name': 'No bump'})
        self.assertEqual(event.ics_sequence, before)

    def test_copy_gets_fresh_uid_and_zero_sequence(self):
        event = self._event()
        event._ensure_ics_uid()
        event.write({'name': 'Bumped'})
        self.assertNotEqual(event.ics_sequence, 0)
        copied = event.copy()
        self.assertFalse(copied.ics_uid)
        self.assertEqual(copied.ics_sequence, 0)
        copied._ensure_ics_uid()
        self.assertNotEqual(copied.ics_uid, event.ics_uid)
