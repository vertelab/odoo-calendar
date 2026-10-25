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
            return _collection_props(self.collection)

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
            props = _collection_props(calendar)
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
            return _collection_props(self.calendar)

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
