# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResourceBooking(TransactionCase):
    """Guards the double-booking detection that used to be broken."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resource = cls.env['resource.resource'].create({
            'name': 'Test projector',
            'resource_type': 'material',
        })
        cls.base = datetime(2026, 1, 1, 9, 0, 0)

    def _event(self, start_offset, duration_hours, name):
        start = self.base + timedelta(hours=start_offset)
        return self.env['calendar.event'].create({
            'name': name,
            'start': start,
            'stop': start + timedelta(hours=duration_hours),
            'resource_ids': [(6, 0, self.resource.ids)],
        })

    def test_no_conflict_when_events_do_not_overlap(self):
        first = self._event(0, 1, 'First')
        second = self._event(2, 1, 'Second')
        self.assertFalse(first.resource_status)
        self.assertFalse(second.resource_status)

    def test_conflict_when_events_overlap(self):
        first = self._event(0, 2, 'First')
        second = self._event(1, 2, 'Second')
        self.assertTrue(
            first.resource_status or second.resource_status,
            "Overlapping events on the same resource must be flagged",
        )

    def test_no_conflict_when_resources_differ(self):
        other = self.env['resource.resource'].create({
            'name': 'Test car',
            'resource_type': 'material',
        })
        start = self.base + timedelta(hours=5)
        first = self.env['calendar.event'].create({
            'name': 'First',
            'start': start,
            'stop': start + timedelta(hours=2),
            'resource_ids': [(6, 0, self.resource.ids)],
        })
        second = self.env['calendar.event'].create({
            'name': 'Second',
            'start': start,
            'stop': start + timedelta(hours=2),
            'resource_ids': [(6, 0, other.ids)],
        })
        self.assertFalse(first.resource_status)
        self.assertFalse(second.resource_status)
