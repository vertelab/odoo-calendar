# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""URL layout and collection lookup for the CalDAV/CardDAV endpoint.

The URL space is:

    /caldav/                          principal + calendar home set
    /caldav/<collection>/             one calendar
    /caldav/<collection>/<uid>.ics    one event
    /caldav/inbox/                    scheduling inbox  (RFC 6638)
    /caldav/outbox/                   scheduling outbox (RFC 6638)

    /carddav/                         addressbook home set
    /carddav/<collection>/            one addressbook
    /carddav/<collection>/<uid>.vcf   one contact

Collections are addressed by their slug (``caldav.collection.slug``), not
by database id: a client that caches a URL must not be pointed at a
different calendar because a row was renumbered.
"""
import logging
import re

from odoo.http import request

_logger = logging.getLogger(__name__)

CALDAV_ROOT = '/caldav'
CARDDAV_ROOT = '/carddav'

# A slug is what we put in the URL: lowercase, digits, dash.
_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')

#: RFC 6638 reserves these two names inside the calendar home set. A
#: collection may never take them, or a client would PUT an event into a
#: URL that means something else.
SCHEDULING_SEGMENTS = ('inbox', 'outbox')


def base_url():
    """Scheme + host, without a trailing slash."""
    return request.httprequest.url_root.rstrip('/')


def root_url(dav_type):
    """The home-set URL for a collection type."""
    # A task collection is a calendar (RFC 4791 §5.2), so it lives under
    # /caldav/ like any other; the slug tells it apart from the event ones.
    root = CARDDAV_ROOT if dav_type == 'addressbook' else CALDAV_ROOT
    return '%s%s' % (base_url(), root)


def collection_url(collection):
    """The collection's own URL."""
    return '%s/%s/' % (root_url(collection.dav_type), collection.slug)


def scheduling_url(dav_type, segment):
    """The scheduling inbox or outbox URL for a collection type."""
    return '%s/%s/' % (root_url(dav_type), segment)


def record_url(collection, record):
    """The URL of one record inside a collection."""
    extension = 'vcf' if collection.dav_type == 'addressbook' else 'ics'
    return '%s%s.%s' % (
        collection_url(collection),
        collection.record_uid(record),
        extension,
    )


def split_path(path):
    """Split a request path into (dav_type, slug, record_uid).

    ``/caldav/work/abc.ics`` → ``('calendar', 'work', 'abc')``
    ``/caldav/``             → ``('calendar', None, None)``
    ``/carddav/contacts/``   → ``('addressbook', 'contacts', None)``

    Returns ``(None, None, None)`` for a path outside both roots.
    """
    path = (path or '').strip('/')
    if not path:
        return None, None, None
    parts = path.split('/')
    root = parts[0]
    if root == 'caldav':
        dav_type = 'calendar'
    elif root == 'carddav':
        dav_type = 'addressbook'
    else:
        return None, None, None

    slug = parts[1] if len(parts) > 1 and parts[1] else None
    record = None
    if len(parts) > 2 and parts[2]:
        filename = parts[2]
        for extension in ('.ics', '.vcf'):
            if filename.endswith(extension):
                record = filename[:-len(extension)]
                break
        else:
            record = filename
    return dav_type, slug, record


def collection_model():
    return request.env['caldav.collection'].sudo()


def find_collection(dav_type, slug):
    """The collection a slug points at, or an empty recordset."""
    if not slug or not _SLUG_RE.match(slug):
        return collection_model().browse()
    return collection_model().search([
        ('dav_type', '=', dav_type),
        ('slug', '=', slug),
        ('active', '=', True),
    ], limit=1)


def collections_for(dav_type, user):
    """Collections of ``dav_type`` the user may see.

    A collection with ``user_id`` set belongs to that user only; an empty
    ``user_id`` is shared. The domain inside the collection decides which
    *records* the user sees — this only decides which collections are
    listed.
    """
    domain = [('dav_type', '=', dav_type), ('active', '=', True)]
    if user:
        domain += ['|', ('user_id', '=', False), ('user_id', '=', user.id)]
    else:
        domain += [('user_id', '=', False)]
    return collection_model().search(domain)


def user_for_request():
    """The authenticated user, or an empty recordset.

    ``_basic_auth`` authenticates against every database in the dbfilter
    list, so ``request.env`` is not guaranteed to be the database the user
    logged into. The uid is what matters.
    """
    return request.env['res.users'].sudo().browse(request.env.uid or 0)


def bind_user(collection, user):
    """Bind a collection to a user for domain evaluation."""
    return collection.with_user_context(user.sudo()) if user else collection
