# -*- coding: utf-8 -*-
# Part of calendar_ics_invitations. See LICENSE file for full copyright and licensing details.

import datetime

import pytz
import vobject
from odoo import fields
from odoo.tests import common


class TestIcsPayload(common.TransactionCase):
    """Assert the iTIP payload itself (task 3.x)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.UTC = pytz.timezone('UTC')
        cls.organizer = cls.env['res.partner'].create({
            'name': 'Anna "A" Andersson, AB',
            'email': 'Anna.Organizer@Example.com',
        })
        cls.organizer_user = cls.env['res.users'].create({
            'name': 'Anna "A" Andersson, AB',
            'login': 'anna.organizer',
            'email': 'Anna.Organizer@Example.com',
            'partner_id': cls.organizer.id,
        })
        cls.attendee_1 = cls.env['res.partner'].create({
            'name': 'Kalle Kula',
            'email': 'Kalle@Example.com',
        })
        cls.attendee_2 = cls.env['res.partner'].create({
            'name': 'Nisse Nilsson',
            'email': 'Nisse@Example.com',
        })
        cls.start = datetime.datetime(2026, 3, 2, 10, 0, 0)
        cls.stop = datetime.datetime(2026, 3, 2, 11, 0, 0)

    def _create_event(self, **kwargs):
        values = {
            'name': 'Design review',
            'start': fields.Datetime.to_string(self.start),
            'stop': fields.Datetime.to_string(self.stop),
            # partner_id is related to user_id.partner_id (the organizer).
            'user_id': self.organizer_user.id,
            'partner_ids': [(6, 0, [self.attendee_1.id, self.attendee_2.id])],
        }
        values.update(kwargs)
        return self.env['calendar.event'].create(values)

    def _payload(self, event, method='REQUEST'):
        raw = event._get_ics_file(method=method)[event.id]
        self.assertIsInstance(raw, bytes)
        return vobject.readOne(raw.decode('utf-8'))

    def test_method_and_prodid(self):
        event = self._create_event()
        for method in ('REQUEST', 'CANCEL'):
            cal = self._payload(event, method=method)
            self.assertEqual(cal.method.value, method)
            self.assertEqual(cal.prodid.value, '-//Vertel//Odoo Calendar//EN')
            self.assertNotIn('PYVOBJECT', cal.prodid.value)

    def test_uid_and_sequence_from_persisted_fields(self):
        event = self._create_event()
        event._ensure_ics_uid()
        cal = self._payload(event)
        self.assertEqual(cal.vevent.uid.value, event.ics_uid)
        self.assertEqual(cal.vevent.sequence.value, str(event.ics_sequence))

    def test_uid_has_no_whitespace(self):
        event = self._create_event()
        event._ensure_ics_uid()
        uid = event.ics_uid
        self.assertNotIn(' ', uid)
        self.assertNotIn('\t', uid)
        self.assertIn('@', uid)

    def test_status_transp_class(self):
        busy_public = self._create_event(show_as='busy', privacy='public')
        cal = self._payload(busy_public)
        self.assertEqual(cal.vevent.status.value, 'CONFIRMED')
        self.assertEqual(cal.vevent.transp.value, 'OPAQUE')
        self.assertEqual(cal.vevent.contents['class'][0].value, 'PUBLIC')

        free_private = self._create_event(show_as='free', privacy='private')
        cal = self._payload(free_private)
        self.assertEqual(cal.vevent.transp.value, 'TRANSPARENT')
        self.assertEqual(cal.vevent.contents['class'][0].value, 'PRIVATE')

        confidential = self._create_event(privacy='confidential')
        cal = self._payload(confidential)
        self.assertEqual(cal.vevent.contents['class'][0].value, 'PRIVATE')

        cancelled = self._payload(free_private, method='CANCEL')
        self.assertEqual(cancelled.vevent.status.value, 'CANCELLED')

    def test_dtstamp_and_last_modified_present(self):
        event = self._create_event()
        cal = self._payload(event)
        self.assertTrue(cal.vevent.dtstamp.value)
        self.assertIn('last-modified', cal.vevent.contents)

    def test_organizer_lowercase_mailto_and_cn_escaping(self):
        event = self._create_event()
        cal = self._payload(event)
        organizer = cal.vevent.organizer
        self.assertEqual(organizer.value, 'mailto:anna.organizer@example.com')
        # vobject cannot emit a double quote in a parameter value, so it is
        # replaced by an apostrophe; the comma is quoted by vobject.
        self.assertEqual(organizer.params['CN'][0], 'Anna \'A\' Andersson, AB')

    def test_attendees_one_line_each_with_params(self):
        event = self._create_event()
        cal = self._payload(event)
        attendees = cal.vevent.contents.get('attendee', [])
        self.assertEqual(len(attendees), 2)
        for line in attendees:
            self.assertTrue(line.value.startswith('mailto:'))
            self.assertNotIn('MAILTO:', line.value)
            self.assertEqual(line.params['ROLE'], ['REQ-PARTICIPANT'])
            self.assertEqual(line.params['RSVP'], ['TRUE'])
            self.assertIn('PARTSTAT', line.params)

    def test_no_duplicate_organizer_or_attendee(self):
        event = self._create_event()
        raw = event._get_ics_file()[event.id].decode('utf-8')
        self.assertEqual(raw.count('ORGANIZER'), 1)
        self.assertEqual(raw.count('ATTENDEE'), 2)
        self.assertNotIn('MAILTO:', raw)

    def test_partstat_mapping(self):
        event = self._create_event()
        mapping = {
            'needsAction': 'NEEDS-ACTION',
            'tentative': 'TENTATIVE',
            'declined': 'DECLINED',
            'accepted': 'ACCEPTED',
        }
        for state, expected in mapping.items():
            event.attendee_ids.write({'state': state})
            cal = self._payload(event)
            by_mail = {
                line.value: line.params['PARTSTAT'][0]
                for line in cal.vevent.contents.get('attendee', [])
            }
            self.assertEqual(by_mail['mailto:kalle@example.com'], expected)

    def test_attendee_without_email_skipped(self):
        no_email = self.env['res.partner'].create({'name': 'No Mail'})
        event = self._create_event(
            partner_ids=[(6, 0, [self.attendee_1.id, no_email.id])])
        cal = self._payload(event)
        attendees = cal.vevent.contents.get('attendee', [])
        self.assertEqual(len(attendees), 1)
        self.assertTrue(all(line.value != 'mailto:' for line in attendees))

    def test_core_content_preserved(self):
        event = self._create_event(
            description='<p>Agenda</p>',
            location='Room 4',
            recurrency=True,
            rrule_type='weekly',
            mon=True,
            count=3,
        )
        alarm = self.env['calendar.alarm'].create({
            'name': 'Reminder', 'alarm_type': 'notification',
            'interval': 'minutes', 'duration': 15,
        })
        event.alarm_ids = [(6, 0, alarm.ids)]
        cal = self._payload(event)
        self.assertEqual(cal.vevent.summary.value, 'Design review')
        self.assertIn('Agenda', cal.vevent.description.value)
        self.assertEqual(cal.vevent.location.value, 'Room 4')
        self.assertTrue(cal.vevent.contents.get('rrule'))
        self.assertTrue(cal.vevent.contents.get('valarm'))

    def test_bytes_roundtrip_and_uid_unfolded(self):
        event = self._create_event()
        event._ensure_ics_uid()
        raw = event._get_ics_file()[event.id]
        cal = vobject.readOne(raw.decode('utf-8'))
        self.assertEqual(cal.vevent.uid.value, event.ics_uid)
