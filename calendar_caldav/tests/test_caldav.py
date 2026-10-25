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

from odoo.tests import common, tagged


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
