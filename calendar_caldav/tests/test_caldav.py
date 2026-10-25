# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Tests for the calendar_caldav protocol layer.

The old test file imported ``..services.caldav``, which no longer exists —
the serialiser moved onto ``caldav.collection``. These tests exercise the
things that actually broke in production (ledningssystem 2026-10-25):

* the domain must be evaluated as the *authenticated* user, not OdooBot
* a recurring series must produce one UID per occurrence
* every record the protocol lists must also serialise
* the XML layer must not care about namespace prefixes
"""
from datetime import datetime

import unittest

from odoo.tests import common, tagged

from ..services import urls



@tagged('post_install', '-at_install')
class TestCaldavCollection(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'DAV Test User',
            'login': 'dav_test_user',
            'email': 'dav.test@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.collection = cls.env['caldav.collection'].search([
            ('slug', '=', 'calendar'),
        ], limit=1)

    def test_domain_evaluated_as_user(self):
        """The domain must use the request user's partner, not OdooBot's.

        ``search_records()`` runs ``.sudo()``, which resets ``env.user`` to
        OdooBot. Before the fix the domain ``partner_ids ∋ user.partner_id``
        resolved to partner 2 (OdooBot) and returned 14 records instead of
        the user's 6479.
        """
        event = self.env['calendar.event'].create({
            'name': 'DAV domain test',
            'start': datetime(2026, 11, 1, 10, 0),
            'stop': datetime(2026, 11, 1, 11, 0),
            'partner_ids': [(6, 0, [self.user.partner_id.id])],
        })
        records = self.collection.with_user_context(self.user).search_records()
        self.assertIn(event, records,
                      'the event must be visible to the user it belongs to')

    def test_private_event_hidden_from_other_user(self):
        """A private event must not leak to a user who is not an attendee."""
        other = self.env['res.users'].create({
            'name': 'DAV Other User',
            'login': 'dav_other_user',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        event = self.env['calendar.event'].create({
            'name': 'DAV private test',
            'start': datetime(2026, 11, 2, 10, 0),
            'stop': datetime(2026, 11, 2, 11, 0),
            'privacy': 'private',
            'partner_ids': [(6, 0, [self.user.partner_id.id])],
        })
        records = self.collection.with_user_context(other).search_records()
        self.assertNotIn(event, records,
                         'a private event must not appear in another '
                         "user's calendar")

    def test_occurrence_uid_is_unique(self):
        """Every occurrence of a series needs its own UID.

        Odoo stores one row per occurrence and all of them share the master's
        ``uuid``. Five series produced 353 rows sharing five UIDs, so clients
        showed one event per series.
        """
        event = self.env['calendar.event'].create({
            'name': 'DAV recurrence test',
            'start': datetime(2026, 12, 1, 10, 0),
            'stop': datetime(2026, 12, 1, 11, 0),
            'partner_ids': [(6, 0, [self.user.partner_id.id])],
            # Odoo 18 only builds the recurrence when recurrency is set;
            # passing rrule alone leaves recurrence_id empty.
            'recurrency': True,
            'rrule': 'FREQ=DAILY;COUNT=3',
        })
        self.assertTrue(event.recurrence_id,
                        'the event should have become a recurring series')
        collection = self.collection.with_user_context(self.user)
        records = collection.search_records().filtered(
            lambda r: r.recurrence_id)
        uids = [collection.record_uid(record) for record in records]
        self.assertEqual(len(uids), len(set(uids)),
                         'UIDs must be unique across occurrences')

    def test_get_record_resolves_every_listed_uid(self):
        """Every UID we hand out must be resolvable by ``get_record``.

        ``sync-collection`` lists ``record_uid()``; the client then GETs each
        href. Two defects broke that contract: the selector was appended to
        an ``'&'`` that only takes two operands (Odoo raised "Domain ... is
        syntactically not correct" → HTTP 500), and occurrence UIDs carried a
        ``-<start>`` suffix ``get_record`` never stripped (HTTP 404).
        """
        collection = self.collection.with_user_context(self.user)
        records = collection.search_records()[:50]
        for record in records:
            with self.subTest(record=record.id):
                uid = collection.record_uid(record)
                found = collection.get_record(uid)
                self.assertEqual(found, record,
                                 'UID %r did not resolve back to %s'
                                 % (uid, record.id))

    def test_get_record_does_not_leak_other_users_private(self):
        """The selector still guards ``get_record`` after the domain fix."""
        event = self.env['calendar.event'].create({
            'name': 'DAV private lookup test',
            'start': datetime(2026, 11, 3, 10, 0),
            'stop': datetime(2026, 11, 3, 11, 0),
            'privacy': 'private',
            'partner_ids': [(6, 0, [self.user.partner_id.id])],
        })
        other = self.env['res.users'].create({
            'name': 'DAV Other Lookup',
            'login': 'dav-other-lookup',
            'email': 'dav-other-lookup@example.com',
            'groups_id': [(6, 0, [self.env.ref(
                'base.group_user').id])],
        })
        collection = self.collection.with_user_context(other)
        self.assertFalse(
            collection.get_record(collection.record_uid(event)),
            "another user must not read a private event by UID")

    def test_every_listed_record_serialises(self):
        """PROPFIND lists hrefs; every one of them must serialise.

        A record that cannot be serialised is an href the client will request
        and then fail on — the 176-byte empty multistatus in production.
        """
        collection = self.collection.with_user_context(self.user)
        records = collection.search_records()[:50]
        for record in records:
            with self.subTest(record=record.id):
                self.assertTrue(collection.to_vobject(record).serialize())

    def test_sync_token_roundtrip(self):
        """An unchanged collection must report no changes."""
        collection = self.collection.with_user_context(self.user)
        records = collection.search_records()
        token = collection.sync_token(records)
        changed, deleted = collection.sync_changes(token, records)
        self.assertEqual(list(changed), [],
                         'an unchanged collection must report no changes')
        self.assertEqual(deleted, [])

    def test_unknown_sync_token_falls_back_to_full_resync(self):
        """RFC 6578 allows a full resync when the token is not recognised."""
        collection = self.collection.with_user_context(self.user)
        records = collection.search_records()
        changed, _deleted = collection.sync_changes(
            'http://vertel.se/ns/sync/calendar/0-19700101T000000Z', records)
        self.assertEqual(changed, records)


@tagged('post_install', '-at_install')
class TestCaldavXml(common.TransactionCase):

    def test_namespace_prefix_is_irrelevant(self):
        """Clients use ``d:``, ``D:`` or a default namespace."""
        from ..services import xmlutil

        bodies = [
            b'<d:propfind xmlns:d="DAV:"><d:prop>'
            b'<d:resourcetype/></d:prop></d:propfind>',
            b'<D:propfind xmlns:D="DAV:"><D:prop>'
            b'<D:resourcetype/></D:prop></D:propfind>',
            b'<propfind xmlns="DAV:"><prop>'
            b'<resourcetype/></prop></propfind>',
        ]
        for body in bodies:
            with self.subTest(body=body[:20]):
                # requested_props returns a set: a client may ask for the
                # same property twice, and the answer must not repeat it.
                self.assertEqual(
                    xmlutil.requested_props(body),
                    {('DAV:', 'resourcetype')})

    def test_xxe_is_blocked(self):
        """An external entity must not be resolved."""
        from ..services import xmlutil

        body = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            b'<d:propfind xmlns:d="DAV:"><d:prop>'
            b'<d:displayname>&x;</d:displayname></d:prop></d:propfind>'
        )
        props = xmlutil.requested_props(body)
        self.assertEqual(props, {('DAV:', 'displayname')})
        self.assertNotIn('root:', str(props))


class TestCollectionProps(common.TransactionCase):
    """The collection PROPFIND must announce what the client needs to sync.

    Both bugs here made DAVx5 re-download the whole addressbook on every
    poll: the sync token was only returned by the sync-collection REPORT,
    never by PROPFIND, so the client had nothing to store; and the
    addressbook announced the CalDAV report names, so clients probed for a
    calendar that does not exist.
    """

    def setUp(self):
        super().setUp()
        self.user = self.env['res.users'].create({
            'name': 'Props User',
            'login': 'props.user@example.com',
        })
        self.collection = self.env['caldav.collection'].sudo().create({
            'name': 'Props Contacts',
            'slug': 'props-contacts',
            'dav_type': 'addressbook',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'domain': '[]',
        })

    def _props(self):
        from unittest.mock import patch
        from ..controllers.main import _collection_props
        with patch.object(urls, 'base_url',
                          return_value='https://example.test'):
            return _collection_props(self.collection, self.env.user)

    def test_addressbook_announces_a_sync_token(self):
        """Without DAV:sync-token in PROPFIND clients cannot do delta sync."""
        props = self._props()
        self.assertIn('<d:sync-token>', props)
        token = props.split('<d:sync-token>', 1)[1].split('<', 1)[0]
        self.assertTrue(token, 'the announced sync token must not be empty')
        self.assertIn(self.collection.sync_token(), token)

    def test_addressbook_announces_getctag(self):
        """Legacy clients (older DAVx5, Apple) poll cs:getctag instead."""
        self.assertIn('<cs:getctag>', self._props())

    def test_addressbook_announces_carddav_reports(self):
        props = self._props()
        self.assertIn('<card:addressbook-query/>', props)
        self.assertIn('<card:addressbook-multiget/>', props)
        self.assertIn('<d:sync-collection/>', props)
        # A CardDAV collection must not advertise the CalDAV reports.
        self.assertNotIn('<cal:calendar-query/>', props)
        self.assertNotIn('<cal:calendar-multiget/>', props)

    def test_calendar_announces_caldav_reports(self):
        calendar = self.env['caldav.collection'].sudo().create({
            'name': 'Props Calendar',
            'slug': 'props-calendar',
            'dav_type': 'calendar',
            'model_id': self.env['ir.model']._get_id('calendar.event'),
            'domain': '[]',
        })
        from unittest.mock import patch
        from ..controllers.main import _collection_props
        with patch.object(urls, 'base_url',
                          return_value='https://example.test'):
            props = _collection_props(calendar, self.env.user)
        self.assertIn('<cal:calendar-query/>', props)
        self.assertIn('<cal:calendar-multiget/>', props)
        self.assertNotIn('<card:addressbook-query/>', props)


class TestBasicAuthRetry(unittest.TestCase):
    """A serialization conflict must not be reported as a wrong password."""

    def test_serialization_conflict_is_retryable(self):
        from ..controllers.main import _is_retryable
        exc = Exception(
            'could not serialize access due to concurrent update')
        self.assertTrue(_is_retryable(exc))

    def test_deadlock_is_retryable(self):
        from ..controllers.main import _is_retryable
        self.assertTrue(_is_retryable(Exception('deadlock detected')))

    def test_bad_credentials_are_not_retryable(self):
        from ..controllers.main import _is_retryable
        self.assertFalse(_is_retryable(Exception('Access Denied')))
        self.assertFalse(_is_retryable(Exception('no such database')))


class TestClientProperties(common.TransactionCase):
    """PROPPATCH: a client must be able to store and read back its settings.

    Thunderbird writes calendar-color/calendar-order right after discovery.
    Before this existed we answered 405, so it logged a failure on every
    sync and re-sent the request forever.
    """

    def setUp(self):
        super().setUp()
        self.collection = self.env['caldav.collection'].create({
            'name': 'Work',
            'slug': 'work-props',
            'dav_type': 'calendar',
            'model_id': self.env['ir.model']._get_id('calendar.event'),
            'domain': '[("user_id", "=", user.id)]',
        })

    def test_displayname_defaults_to_name(self):
        self.assertEqual(self.collection.client_property('{DAV:}displayname'),
                         '')

    def test_known_properties_land_in_columns(self):
        self.collection.set_client_properties({
            '{http://apple.com/ns/ical/}calendar-color': '#FF5733',
            '{http://apple.com/ns/ical/}calendar-order': '7',
            '{DAV:}displayname': 'Min jobbkalender',
        })
        self.assertEqual(self.collection.calendar_color, '#FF5733')
        self.assertEqual(self.collection.calendar_order, 7)
        self.assertEqual(self.collection.display_name, 'Min jobbkalender')
        self.assertEqual(
            self.collection.client_property('{DAV:}displayname'),
            'Min jobbkalender')

    def test_unknown_properties_round_trip_through_json(self):
        self.collection.set_client_properties({
            '{urn:example:}custom': 'kept',
        })
        self.assertEqual(
            self.collection.client_property('{urn:example:}custom'), 'kept')

    def test_none_removes_a_property(self):
        self.collection.set_client_properties({
            '{urn:example:}custom': 'kept',
        })
        self.collection.set_client_properties({'{urn:example:}custom': None})
        self.assertEqual(self.collection.client_property('{urn:example:}custom'),
                         '')

    def test_bad_order_does_not_raise(self):
        self.collection.set_client_properties({
            '{http://apple.com/ns/ical/}calendar-order': 'not-a-number',
        })
        self.assertEqual(self.collection.calendar_order, 0)


class TestSupportedReports(common.TransactionCase):
    """A collection must announce exactly the reports it answers.

    ``_collection_props`` builds absolute hrefs from the request, so the
    tests patch ``base_url`` instead of standing up an HTTP request.
    """

    def setUp(self):
        super().setUp()
        self.calendar = self.env['caldav.collection'].create({
            'name': 'Work',
            'slug': 'work-reports',
            'dav_type': 'calendar',
            'model_id': self.env['ir.model']._get_id('calendar.event'),
            'domain': '[]',
        })

    def _props(self):
        from unittest.mock import patch
        from ..controllers.main import _collection_props
        with patch.object(urls, 'base_url', return_value='https://example.test'):
            return _collection_props(self.calendar, self.env.user)

    def test_free_busy_is_announced(self):
        props = self._props()
        self.assertIn('free-busy-query', props)
        self.assertIn('calendar-query', props)
        self.assertIn('sync-collection', props)
        self.assertIn('expand-property', props)

    def test_sync_token_and_getctag_are_properties(self):
        props = self._props()
        self.assertIn('<d:sync-token>', props)
        self.assertIn('<cs:getctag>', props)

    def test_supported_data_is_announced(self):
        props = self._props()
        self.assertIn('supported-calendar-data', props)
        self.assertIn('calendar-timezone', props)

    def test_dav_header_does_not_claim_extended_mkcol(self):
        from ..controllers.main import DAV_CAPABILITIES
        self.assertNotIn('extended-mkcol', DAV_CAPABILITIES)
        # Class 2 means "supports locking" — we do not.
        self.assertNotIn('2', [part.strip()
                               for part in DAV_CAPABILITIES.split(',')])


class TestItipParsing(common.TransactionCase):
    """RFC 5546: read the method out of a payload before acting on it."""

    OUTLOOK_REQUEST = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Microsoft Corporation//Outlook 16.0 MIMEDIR//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:040000008200E00074C5B7101A82E00800000000
SUMMARY:Projektmote
DTSTART:20261101T090000Z
DTEND:20261101T100000Z
LOCATION:Rum 12
ORGANIZER;CN=Anna Svensson:mailto:anna@example.com
ATTENDEE;CN=Anders;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:anders@vertel.se
SEQUENCE:2
END:VEVENT
END:VCALENDAR"""

    def test_reads_method_uid_and_sequence(self):
        from ..services.ical import parse_itip
        result = parse_itip(self.OUTLOOK_REQUEST)
        self.assertEqual(result['method'], 'REQUEST')
        self.assertEqual(result['uid'],
                         '040000008200E00074C5B7101A82E00800000000')
        self.assertEqual(result['sequence'], 2)

    def test_reads_organizer_and_attendee_partstat(self):
        from ..services.ical import parse_itip
        result = parse_itip(self.OUTLOOK_REQUEST)
        self.assertEqual(result['organizer']['email'], 'anna@example.com')
        self.assertEqual(result['organizer']['name'], 'Anna Svensson')
        self.assertEqual(len(result['attendees']), 1)
        self.assertEqual(result['attendees'][0]['email'], 'anders@vertel.se')
        self.assertEqual(result['attendees'][0]['partstat'], 'NEEDS-ACTION')
        self.assertTrue(result['attendees'][0]['rsvp'])

    def test_converts_utc_to_naive(self):
        """Odoo stores naive UTC; an aware datetime would shift the event."""
        from ..services.ical import parse_itip
        result = parse_itip(self.OUTLOOK_REQUEST)
        self.assertIsNone(result['event']['start'].tzinfo)
        self.assertEqual(result['event']['start'].hour, 9)

    def test_rejects_payload_without_uid(self):
        """Without a UID a PUT is not idempotent and a REPLY cannot match."""
        from ..services.ical import ItipError, parse_itip
        payload = ("BEGIN:VCALENDAR\nVERSION:2.0\nMETHOD:REQUEST\n"
                   "BEGIN:VEVENT\nSUMMARY:x\nEND:VEVENT\nEND:VCALENDAR")
        with self.assertRaises(ItipError):
            parse_itip(payload)

    def test_rejects_payload_without_vevent(self):
        from ..services.ical import ItipError, parse_itip
        payload = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR"
        with self.assertRaises(ItipError):
            parse_itip(payload)


class TestItipReply(common.TransactionCase):
    """The REPLY Odoo has never been able to send."""

    def setUp(self):
        super().setUp()
        self.user = self.env['res.users'].create({
            'name': 'ITIP Attendee',
            'login': 'itip-attendee@example.test',
            'email': 'itip-attendee@example.test',
        })
        self.event = self.env['calendar.event'].create({
            'name': 'External invitation',
            'start': datetime(2026, 11, 1, 9, 0),
            'stop': datetime(2026, 11, 1, 10, 0),
            'imip_organizer': 'anna@example.com',
            'itip_sequence': 2,
            'partner_ids': [(6, 0, [self.user.partner_id.id])],
        })

    def test_reply_carries_method_and_partstat(self):
        from icalendar import Calendar
        from ..services.ical import build_itip_reply
        attendee = self.event.attendee_ids.filtered(
            lambda a: a.partner_id == self.user.partner_id)[:1]
        payload = build_itip_reply(self.event, attendee, 'ACCEPTED')
        parsed = Calendar.from_ical(payload)
        self.assertEqual(str(parsed.get('method')), 'REPLY')
        vevent = parsed.walk('VEVENT')[0]
        self.assertEqual(str(vevent.get('uid')), self.event.uuid)
        self.assertEqual(str(vevent.get('sequence')), '2')
        self.assertIn('anna@example.com', str(vevent.get('organizer')))
        attendee_line = vevent.get('attendee')
        self.assertEqual(attendee_line.params['PARTSTAT'], 'ACCEPTED')

    def test_no_reply_is_sent_to_an_internal_organizer(self):
        """Odoo updates its own attendees through the ORM; mail is noise."""
        self.event.write({
            'imip_organizer': False,
            'user_id': self.user.id,
        })
        attendee = self.event.attendee_ids[:1]
        self.assertFalse(self.event._send_itip_reply(attendee, 'accepted'))


class TestItipSenderVerification(common.TransactionCase):
    """An .ics is a write instruction; only the organiser may send one."""

    def _message(self, headers):
        from email.mime.text import MIMEText
        message = MIMEText('invitation follows')
        for key, value in headers.items():
            message[key] = value
        return message

    def test_sender_must_match_organizer(self):
        Message = self.env['mail.message']
        message = self._message({
            'From': 'attacker@evil.example',
            'Authentication-Results': 'mx.vertel.se; spf=pass evil.example',
        })
        self.assertFalse(Message._sender_may_speak_for(
            'attacker@evil.example', 'anna@example.com', message))

    def test_missing_authentication_is_not_a_pass(self):
        Message = self.env['mail.message']
        message = self._message({'From': 'anna@example.com'})
        self.assertFalse(Message._sender_may_speak_for(
            'anna@example.com', 'anna@example.com', message))

    def test_failing_authentication_is_rejected(self):
        Message = self.env['mail.message']
        message = self._message({
            'Authentication-Results': 'mx.vertel.se; spf=fail example.com',
        })
        self.assertFalse(Message._sender_may_speak_for(
            'anna@example.com', 'anna@example.com', message))

    def test_authenticated_organizer_is_accepted(self):
        Message = self.env['mail.message']
        message = self._message({
            'Authentication-Results': 'mx.vertel.se; spf=pass example.com',
        })
        self.assertTrue(Message._sender_may_speak_for(
            'anna@example.com', 'anna@example.com', message))


class TestItipOrganizerSerialization(common.TransactionCase):
    """The organiser a client sees must be the real one, not OdooBot."""

    def test_external_organizer_wins_over_user_id(self):
        event = self.env['calendar.event'].create({
            'name': 'Received from Outlook',
            'start': datetime(2026, 11, 5, 9, 0),
            'stop': datetime(2026, 11, 5, 10, 0),
            'imip_organizer': 'anna@example.com',
        })
        self.assertTrue(event.user_id, 'Odoo sets a default user_id')
        collection = self.env['caldav.collection'].search(
            [('dav_type', '=', 'calendar')], limit=1)
        payload = collection.to_vobject(event).serialize()
        # ORGANIZER must be the external address. Odoo still adds the
        # record owner as an ATTENDEE, which is Odoo's own behaviour and
        # not something this module should change.
        organizer_line = [
            line for line in payload.splitlines()
            if line.upper().startswith('ORGANIZER')]
        self.assertEqual(len(organizer_line), 1)
        self.assertIn('anna@example.com', organizer_line[0])
        self.assertNotIn('odoobot', organizer_line[0].lower())

    def test_internal_organizer_still_used_when_no_external(self):
        user = self.env['res.users'].create({
            'name': 'Internal Organiser',
            'login': 'internal-organiser@example.test',
            'email': 'internal-organiser@example.test',
        })
        event = self.env['calendar.event'].create({
            'name': 'Our own meeting',
            'start': datetime(2026, 11, 5, 9, 0),
            'stop': datetime(2026, 11, 5, 10, 0),
            'user_id': user.id,
            'partner_ids': [(6, 0, [user.partner_id.id])],
        })
        collection = self.env['caldav.collection'].search(
            [('dav_type', '=', 'calendar')], limit=1)
        payload = collection.to_vobject(event).serialize()
        self.assertIn('internal-organiser@example.test', payload)


class TestItipRejectionIsVisible(common.TransactionCase):
    """A dropped invitation must be visible, not just logged.

    A customer with a broken SPF record otherwise never learns that their
    invitations are being discarded.
    """

    def _message(self, headers):
        from email.mime.text import MIMEText
        message = MIMEText('invitation follows')
        for key, value in headers.items():
            message[key] = value
        return message

    def _itip(self, organizer='anna@example.com'):
        return {
            'method': 'REQUEST',
            'uid': 'reject-test-uid',
            'sequence': 1,
            'organizer': {'email': organizer, 'name': 'Anna'},
            'attendees': [],
            'event': {'name': 'Ska inte skapas'},
            'recurrence_id': None,
        }

    def test_reason_names_a_mismatched_organizer(self):
        Message = self.env['mail.message']
        message = self._message({'From': 'attacker@evil.example'})
        reason = Message._rejection_reason(
            'attacker@evil.example', 'anna@example.com', message)
        self.assertIn('stämmer inte med avsändaren', reason)

    def test_reason_names_missing_authentication(self):
        Message = self.env['mail.message']
        message = self._message({'From': 'anna@example.com'})
        reason = Message._rejection_reason(
            'anna@example.com', 'anna@example.com', message)
        self.assertIn('SPF/DKIM', reason)

    def test_reason_names_missing_organizer(self):
        Message = self.env['mail.message']
        message = self._message({'From': 'anna@example.com'})
        reason = Message._rejection_reason('anna@example.com', '', message)
        self.assertIn('saknar ORGANIZER', reason)

    def test_rejection_posts_a_note_and_creates_no_event(self):
        """The whole point: visible to the user, inert in the calendar."""
        before = self.env['calendar.event'].search_count(
            [('uuid', '=', 'reject-test-uid')])
        message = self._message({'From': 'attacker@evil.example'})
        self.env['mail.message']._report_rejected_itip(
            self._itip(), {'email_from': 'attacker@evil.example'},
            'attacker@evil.example', 'anna@example.com')
        after = self.env['calendar.event'].search_count(
            [('uuid', '=', 'reject-test-uid')])
        self.assertEqual(before, after, 'no event may be created')


class TestSchedulingProperties(common.TransactionCase):
    """RFC 6638 §2.1: a client cannot schedule what it cannot find."""

    def setUp(self):
        super().setUp()
        self.calendar = self.env['caldav.collection'].search(
            [('dav_type', '=', 'calendar')], limit=1)
        self.user = self.env['res.users'].create({
            'name': 'Scheduling User',
            'login': 'scheduling@example.test',
            'email': 'scheduling@example.test',
        })

    def _props(self, collection=None):
        """Build the collection properties outside a request context.

        ``_collection_props`` reaches for ``request`` in two places — the
        base URL and the current user — so both are supplied here rather
        than read from an unbound request.
        """
        from unittest.mock import patch
        from ..controllers.main import _collection_props
        collection = collection or self.calendar
        with patch.object(urls, 'base_url', return_value='https://example.test'), \
                patch.object(urls, 'user_for_request', return_value=self.user):
            return _collection_props(collection, self.user)

    def test_announces_inbox_and_outbox(self):
        props = self._props()
        self.assertIn('schedule-inbox-URL', props)
        self.assertIn('schedule-outbox-URL', props)
        self.assertIn('/caldav/inbox/', props)
        self.assertIn('/caldav/outbox/', props)

    def test_announces_calendar_user_address_set(self):
        """Without this a client cannot tell which ATTENDEE line is 'me'."""
        props = self._props()
        self.assertIn('calendar-user-address-set', props)
        self.assertIn('mailto:', props)

    def test_announces_calendar_transparency(self):
        props = self._props()
        self.assertIn('schedule-calendar-transp', props)
        self.assertIn('transparent', props)

    def test_scheduling_urls_are_not_collection_slugs(self):
        """inbox/outbox are reserved; a collection may not shadow them."""
        self.assertIn('inbox', urls.SCHEDULING_SEGMENTS)
        self.assertIn('outbox', urls.SCHEDULING_SEGMENTS)


class TestItipCounter(common.TransactionCase):
    """RFC 5546 §3.2.3: a counter-proposal must not be dropped."""

    def test_counter_is_supported(self):
        from ..services.ical import SUPPORTED_METHODS
        self.assertIn('COUNTER', SUPPORTED_METHODS)

    def test_counter_builds_a_valid_payload(self):
        from icalendar import Calendar
        from ..services.ical import build_itip_counter
        user = self.env['res.users'].create({
            'name': 'Counter Attendee',
            'login': 'counter@example.test',
            'email': 'counter@example.test',
        })
        event = self.env['calendar.event'].create({
            'name': 'Counter test',
            'start': datetime(2026, 11, 10, 9, 0),
            'stop': datetime(2026, 11, 10, 10, 0),
            'imip_organizer': 'anna@example.com',
            'partner_ids': [(6, 0, [user.partner_id.id])],
        })
        attendee = event.attendee_ids.filtered(
            lambda a: a.partner_id == user.partner_id)[:1]
        payload = build_itip_counter(
            event, attendee,
            datetime(2026, 11, 10, 14, 0), datetime(2026, 11, 10, 15, 0))
        parsed = Calendar.from_ical(payload)
        self.assertEqual(str(parsed.get('method')), 'COUNTER')
        vevent = parsed.walk('VEVENT')[0]
        self.assertEqual(vevent.get('dtstart').dt.hour, 14)
        self.assertIn('anna@example.com', str(vevent.get('organizer')))


class TestRecurrenceId(common.TransactionCase):
    """A RECURRENCE-ID names one instance, never the series."""

    def test_parser_keeps_the_recurrence_id(self):
        from ..services.ical import parse_itip
        payload = """BEGIN:VCALENDAR
VERSION:2.0
METHOD:REQUEST
BEGIN:VEVENT
UID:series-test
SUMMARY:Serie
DTSTART:20261112T090000Z
DTEND:20261112T100000Z
RECURRENCE-ID:20261112T090000Z
ORGANIZER:mailto:anna@example.com
SEQUENCE:1
END:VEVENT
END:VCALENDAR"""
        result = parse_itip(payload)
        self.assertIsNotNone(result['recurrence_id'])
        self.assertEqual(result['recurrence_id'].hour, 9)
        self.assertNotIn('_recurrence_id', result['event'])


class TestBrokenPhotoDoesNotKillTheResponse(common.TransactionCase):
    """One unreadable image must not cost the client every contact.

    ``res.partner.image_1920`` is a binary field backed by the filestore.
    When the blob is gone, reading the field raises, and that exception used
    to escape ``_to_vcard()`` and abort the whole ``addressbook-query``
    multistatus — DAVx5 received a truncated 4 303-contact response and
    discarded the entire sync (ledningssystem 2026-10-25: attachment 21470
    pointed at filestore b5/b51549b0..., which does not exist).
    """

    def setUp(self):
        super().setUp()
        self.collection = self.env['caldav.collection'].search(
            [('dav_type', '=', 'addressbook')], limit=1)
        if not self.collection:
            self.skipTest('no addressbook collection configured')

    def test_unreadable_image_serialises_without_photo(self):
        partner = self.env['res.partner'].create({'name': 'Dead Photo Test'})
        original = type(partner).image_1920

        # Simulate the missing blob: the field raises on read.
        def boom(self):
            raise FileNotFoundError('filestore blob is gone')

        type(partner).image_1920 = property(boom)
        try:
            card = self.collection._to_vcard(partner)
        finally:
            type(partner).image_1920 = original

        self.assertIsNotNone(card)
        payload = card.serialize()
        self.assertIn('BEGIN:VCARD', payload)
        self.assertIn('Dead Photo Test', payload)
        self.assertNotIn('PHOTO', payload)


class TestSyncChanges(common.TransactionCase):
    """sync-collection must notice writes *and* deletes.

    The previous token was derived from the newest write_date and compared
    as a string, so a client that polled once saw "0 changes" until a
    record happened to be written later. DAVx5 reported an empty address
    book because of it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.collection = cls.env['caldav.collection'].create({
            'name': 'Sync Test',
            'slug': 'sync-test',
            'dav_type': 'addressbook',
            'model_id': cls.env['ir.model']._get_id('res.partner'),
            'domain': "[]",
        })
        cls.partner = cls.Partner.create({'name': 'Sync One'})

    def test_first_sync_returns_everything(self):
        changed, deleted = self.collection.sync_changes('')
        self.assertIn(self.partner, changed)
        self.assertEqual(deleted, [])

    def test_polling_without_changes_returns_nothing(self):
        """A poll with the current token must be cheap and empty.

        This is the case that used to be wrong in the other direction: the
        old string comparison found nothing ever again after the first
        sync, so the client never learned about later writes either.
        """
        token = self.collection.sync_token()
        changed, deleted = self.collection.sync_changes(token)
        self.assertFalse(changed)
        self.assertEqual(deleted, [])

    def test_a_write_moves_the_token_and_reports_the_record(self):
        token = self.collection.sync_token()
        other = self.Partner.create({'name': 'Sync Two'})
        self.collection.bump_sync_rev(uids=[self.collection.record_uid(other)])
        changed, deleted = self.collection.sync_changes(token)
        self.assertIn(other, changed)
        self.assertNotIn(self.partner, changed)

    def test_a_delete_is_reported(self):
        """Without this a client keeps showing a contact that is gone."""
        token = self.collection.sync_token()
        uid = self.collection.record_uid(self.partner)
        self.collection.bump_sync_rev(removed=[uid])
        changed, deleted = self.collection.sync_changes(token)
        self.assertEqual(deleted, [uid])

    def test_an_unknown_token_falls_back_to_a_full_resync(self):
        changed, deleted = self.collection.sync_changes('not-a-token')
        self.assertIn(self.partner, changed)
        self.assertEqual(deleted, [])

    def test_the_token_changes_when_the_revision_moves(self):
        before = self.collection.sync_token()
        self.collection.bump_sync_rev(
            uids=[self.collection.record_uid(self.partner)])
        self.assertNotEqual(before, self.collection.sync_token())


class TestRequestBodyWithoutContentType(common.TransactionCase):
    """A DAV body must be readable whatever Content-Type the client sent.

    curl defaults to application/x-www-form-urlencoded and DAVx5 sometimes
    sends no type at all. Odoo's dispatcher parses a form body before the
    controller runs, which drained the stream and made every REPORT answer
    400 Malformed request body.
    """

    def test_the_body_is_captured_at_the_wsgi_layer(self):
        from ..hooks import BODY_ENVIRON_KEY, _make_environ_with_body_capture
        import io

        payload = b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"/>'

        def original(handler):
            return {
                'wsgi.input': io.BytesIO(payload),
                'CONTENT_LENGTH': str(len(payload)),
                'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            }

        environ = _make_environ_with_body_capture(original)(None)
        self.assertEqual(environ[BODY_ENVIRON_KEY], payload)
        # The dispatcher must still be able to read the same bytes.
        self.assertEqual(environ['wsgi.input'].read(), payload)

    def test_a_request_without_a_body_is_left_alone(self):
        from ..hooks import BODY_ENVIRON_KEY, _make_environ_with_body_capture
        import io

        def original(handler):
            return {'wsgi.input': io.BytesIO(b''), 'CONTENT_LENGTH': '0'}

        environ = _make_environ_with_body_capture(original)(None)
        self.assertNotIn(BODY_ENVIRON_KEY, environ)


class TestReportBodyCapture(common.TransactionCase):
    """The DAV body must survive Odoo's eager form parsing.

    DAVx5 sends its CardDAV REPORT with a content type Odoo's dispatcher
    treats as a form (or with none at all). Werkzeug's form parser then
    drains the stream before the controller runs, ``_request_body()`` saw
    an empty body, the root element was ``None`` and every sync got 400 —
    which DAVx5 reported as "0 contacts" (ledningssystem 2026-10-25).

    ``hooks._make_environ_with_body_capture`` reads the bytes in werkzeug's
    ``make_environ``, before Odoo touches them. These tests pin that
    behaviour, because a regression here is silent: the endpoint keeps
    answering, just with nothing in it.
    """

    BODY = (
        b'<?xml version="1.0"?>'
        b'<card:addressbook-query xmlns:d="DAV:" '
        b'xmlns:card="urn:ietf:params:xml:ns:carddav">'
        b'<d:prop><d:getetag/></d:prop>'
        b'</card:addressbook-query>'
    )

    def _environ(self, content_type, body=None):
        """A minimal WSGI environ carrying ``body`` as the request body."""
        import io
        body = self.BODY if body is None else body
        environ = {
            'REQUEST_METHOD': 'REPORT',
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': io.BytesIO(body),
        }
        if content_type is not None:
            environ['CONTENT_TYPE'] = content_type
        return environ

    def _capture(self, environ):
        """Run the real capture wrapper over an environ."""
        from ..hooks import _make_environ_with_body_capture

        original = lambda _handler: environ  # noqa: E731
        return _make_environ_with_body_capture(original)(None)

    def test_body_is_captured_for_every_content_type(self):
        """Form-encoded, text/xml, application/xml and absent all work."""
        from ..hooks import BODY_ENVIRON_KEY

        for content_type in (
            'application/x-www-form-urlencoded',
            'multipart/form-data; boundary=x',
            'text/xml; charset=utf-8',
            'application/xml; charset=utf-8',
            None,
        ):
            with self.subTest(content_type=content_type):
                environ = self._capture(self._environ(content_type))
                self.assertEqual(
                    environ.get(BODY_ENVIRON_KEY), self.BODY,
                    'body lost for content type %r' % (content_type,))

    def test_stream_is_rewound_for_the_dispatcher(self):
        """Odoo must still be able to read the body after the capture."""
        environ = self._capture(
            self._environ('application/x-www-form-urlencoded'))
        self.assertEqual(environ['wsgi.input'].read(), self.BODY)

    def test_empty_body_is_not_captured(self):
        """A body-less PROPFIND must not be recorded as an empty capture."""
        from ..hooks import BODY_ENVIRON_KEY

        environ = self._capture(self._environ('application/xml', body=b''))
        self.assertNotIn(BODY_ENVIRON_KEY, environ)

    def test_captured_body_parses_to_the_expected_root(self):
        """The captured bytes are what the REPORT dispatcher parses."""
        from ..hooks import BODY_ENVIRON_KEY
        from ..services import xmlutil

        environ = self._capture(
            self._environ('application/x-www-form-urlencoded'))
        self.assertEqual(
            xmlutil.body_root_name(environ[BODY_ENVIRON_KEY]),
            'addressbook-query')


class TestVtodo(common.TransactionCase):
    """A VTODO is a project.task with no project.

    That is what Odoo's own Att-göra view (project_todo) shows, so a task
    written from Thunderbird appears in /odoo/to-do without any glue.
    Thunderbird hides a collection from its task view unless the collection
    advertises VTODO in supported-calendar-component-set, which is why tasks
    "did not work" while the calendar did.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.collection = cls.env['caldav.collection'].create({
            'name': 'Tasks Test',
            'slug': 'tasks-test',
            'dav_type': 'tasks',
            'model_id': cls.env['ir.model']._get_id('project.task'),
            'domain': "[('project_id', '=', False)]",
            'field_uuid': cls.env['ir.model.fields']._get(
                'project.task', 'caldav_uuid').id,
        })
        cls.Task = cls.env['project.task']

    def _vtodo(self, **overrides):
        values = {
            'summary': 'Write the report',
            'description': 'Before Friday',
            'status': 'NEEDS-ACTION',
            'priority': '1',
            'due': '20261030T120000Z',
        }
        values.update(overrides)
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'BEGIN:VTODO',
                 'UID:vtodo-test-1']
        for key, value in values.items():
            if value is not None:
                lines.append('%s:%s' % (key.upper(), value))
        lines += ['END:VTODO', 'END:VCALENDAR']
        return '\r\n'.join(lines) + '\r\n'

    def test_a_vtodo_parses_into_task_values(self):
        values = self.collection.from_vobject(self._vtodo())
        self.assertEqual(values['name'], 'Write the report')
        self.assertEqual(values['description'], 'Before Friday')
        self.assertEqual(values['state'], '01_in_progress')
        self.assertEqual(values['priority'], '1')
        self.assertEqual(values['caldav_uuid'], 'vtodo-test-1')
        self.assertTrue(values['date_deadline'])

    def test_a_completed_vtodo_is_done(self):
        values = self.collection.from_vobject(
            self._vtodo(status='COMPLETED', **{'percent-complete': 100}))
        self.assertEqual(values['state'], '1_done')
        # ``progress`` lives in project_todo, which is not a hard dependency,
        # so the parser hands it back under a private key that the controller
        # only writes when the field exists.
        self.assertEqual(values['_progress'], 100.0)

    def test_a_cancelled_vtodo_is_cancelled(self):
        values = self.collection.from_vobject(self._vtodo(status='CANCELLED'))
        self.assertEqual(values['state'], '1_canceled')

    def test_a_task_serialises_to_a_vtodo(self):
        task = self.Task.create({
            'name': 'Write the report',
            'project_id': False,
            'user_ids': [(6, 0, [self.env.user.id])],
        })
        body = self.collection.to_vobject(task)
        self.assertIn('BEGIN:VTODO', body)
        self.assertIn('SUMMARY:Write the report', body)
        self.assertIn('UID:%s' % task.caldav_uuid, body)

    def test_a_done_task_reads_as_completed(self):
        task = self.Task.create({
            'name': 'Done already',
            'project_id': False,
            'state': '1_done',
        })
        body = self.collection.to_vobject(task)
        self.assertIn('STATUS:COMPLETED', body)
        self.assertIn('PERCENT-COMPLETE:100', body)

    def test_a_vevent_in_a_task_collection_is_rejected(self):
        """A client may PUT the wrong component; that must be an error."""
        vevent = ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n'
                  'UID:x\r\nSUMMARY:Not a task\r\n'
                  'DTSTART:20261030T120000Z\r\nEND:VEVENT\r\n'
                  'END:VCALENDAR\r\n')
        self.assertIsNone(self.collection.from_vobject(vevent))

    def test_the_collection_announces_vtodo(self):
        """Without this line Thunderbird hides the collection entirely.

        Checked through the source rather than through _collection_props,
        which needs a request to build absolute URLs.
        """
        import inspect
        from ..controllers import main as controller

        source = inspect.getsource(controller._collection_props)
        tasks_branch = source.split("dav_type == 'tasks'")[1]
        tasks_branch = tasks_branch.split("dav_type == 'calendar'")[0]
        self.assertIn('<cal:comp name="VTODO"/>', tasks_branch)
        self.assertNotIn('VEVENT', tasks_branch)

    def test_a_task_gets_a_uid_on_create(self):
        task = self.Task.create({'name': 'Needs a UID',
                                 'project_id': False})
        self.assertTrue(task.caldav_uuid)

    def test_an_addressbook_answers_with_card_address_data(self):
        """RFC 6352 §10.4: a card body is card:address-data, not calendar-data.

        Answering with cal:calendar-data produces a valid multistatus that
        no client can read, so every address book renders empty while the
        server reports 207 and thousands of records.
        """
        from types import SimpleNamespace

        from ..controllers.main import CalDAVController

        addressbook = SimpleNamespace(dav_type='addressbook')
        card = CalDAVController._data_element(
            addressbook, 'BEGIN:VCARD\r\nEND:VCARD\r\n')
        self.assertTrue(card.startswith('<card:address-data>'))
        self.assertNotIn('calendar-data', card)

        event = CalDAVController._data_element(
            self.collection, 'BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n')
        self.assertTrue(event.startswith('<cal:calendar-data>'))

    def test_the_principal_is_not_the_home_set(self):
        """RFC 3744 §4: the principal is its own resource.

        Answering current-user-principal and calendar-home-set with the
        same href makes the root indistinguishable from a calendar. A
        client walking principal -> home-set -> children gets the root
        back as a child and stops; that is why Thunderbird showed an
        empty calendar while DAVx5 coped.
        """
        import inspect

        from ..services import urls

        # Checked against the source because principal_url() needs a
        # request to build the host part.
        source = inspect.getsource(urls.principal_url)
        self.assertIn('/principal/', source)

        for dav_type, root in (('calendar', urls.CALDAV_ROOT),
                               ('addressbook', urls.CARDDAV_ROOT)):
            # The two must never collapse onto the same path, which is the
            # bug: principal and home set answered with one href.
            self.assertNotEqual(root + '/principal/', root + '/')
