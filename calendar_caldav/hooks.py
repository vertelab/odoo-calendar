# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Hooks for calendar_caldav."""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Backfill event UUIDs and import collections from the Radicale track.

    Both steps are idempotent: the module may be upgraded (not only
    installed) and the hook runs again.
    """
    _backfill_event_uuids(env)
    _backfill_partner_uuids(env)
    _link_uuid_fields(env)


def _backfill_event_uuids(env):
    """Every event needs a stable UID before a client can sync it."""
    env.cr.execute(
        "UPDATE calendar_event SET uuid = gen_random_uuid()::text "
        "WHERE uuid IS NULL"
    )
    count = env.cr.rowcount
    if count:
        _logger.info('calendar_caldav: backfilled uuid on %s events', count)


def _backfill_partner_uuids(env):
    """Give every contact a stable CardDAV UID.

    Without this the UID fell back to the database id, which changes on a
    merge and is not what the client stored. Done in SQL because there are
    thousands of partners and no business logic is involved.
    """
    env.cr.execute(
        "UPDATE res_partner SET caldav_uuid = gen_random_uuid()::text "
        "WHERE caldav_uuid IS NULL"
    )
    count = env.cr.rowcount
    if count:
        _logger.info('calendar_caldav: backfilled caldav_uuid on %s partners',
                     count)


def _link_uuid_fields(env):
    """Point each shipped collection at its model's DAV UID field.

    data/caldav_collection_data.xml is ``noupdate="1"`` so an upgrade does
    not rewrite it — which is right for the domains (an operator may have
    edited them) but wrong for field_uuid, added after the collections
    already existed. Setting it here keeps both properties.
    """
    for collection in env['caldav.collection'].sudo().search([]):
        if collection.field_uuid:
            continue
        field = env['ir.model.fields'].sudo().search([
            ('model', '=', collection.model_name),
            ('name', '=', 'caldav_uuid'),
        ], limit=1)
        if field:
            collection.field_uuid = field.id
            _logger.info('calendar_caldav: linked %s to %s',
                         collection.slug, field.name)


# Removed 2026-10-25: _migrate_dav_collections() imported dav.collection rows
# from the Radicale track. It is gone because (a) it ran once, on a database
# that no longer exists in that state, and (b) it was the only thing keeping
# a dependency on base_dav. The curated collections in
# data/caldav_collection_data.xml are the authoritative set.
