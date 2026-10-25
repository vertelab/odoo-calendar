# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""CalDAV/CardDAV endpoint.

URL space (see ``services/urls.py``)::

    /.well-known/{caldav,carddav}          discovery, both slash forms
                                           (webdav belongs to dms_webdav)
    /caldav/                               principal + calendar home set
    /caldav/<slug>/                        one calendar
    /caldav/<slug>/<uid>.ics               one event
    /carddav/                              addressbook home set
    /carddav/<slug>/                       one addressbook
    /carddav/<slug>/<uid>.vcf              one contact

Two rules run through the whole file:

1. **The collection's domain is evaluated as the authenticated user.**
   ``caldav.collection.search_records()`` calls ``sudo()`` internally, so
   the user has to be handed over in the context (``with_user_context``).
   Without that the domain is evaluated as OdooBot and every user sees
   OdooBot's records — the defect that made the Radicale track return an
   empty multistatus.

2. **Never ``search([])``.** Every record comes from a collection, and
   every collection carries a domain. A bare search would hand out other
   people's private events.
"""
import base64
import logging
import time
import uuid
from datetime import datetime

from odoo import api, http
from odoo.http import request
from odoo.service import db

from ..services import urls, xmlutil
from ..services.caldav import icalendar_to_odoo_event
from ..services.ical import (
    PARTSTAT_TO_STATE,
    SUPPORTED_METHODS,
    ItipError,
    parse_itip,
)

_logger = logging.getLogger(__name__)

AUTH_HEADER = 'Basic realm="Odoo CalDAV", charset="UTF-8"'

# Parallel DAV requests authenticate against the same res_users row; see
# _basic_auth() for why a conflict must not be reported as a 401.
AUTH_RETRIES = 3
AUTH_RETRY_DELAY = 0.15

# Defaults announced for a calendar that the client has not configured yet.
DEFAULT_CALENDAR_COLOR = '#2A6B9C'
DEFAULT_TIMEZONE = (
    'BEGIN:VCALENDAR\r\n'
    'VERSION:2.0\r\n'
    'PRODID:-//Vertel//Odoo CalDAV//EN\r\n'
    'BEGIN:VTIMEZONE\r\n'
    'TZID:Europe/Stockholm\r\n'
    'X-LIC-LOCATION:Europe/Stockholm\r\n'
    'BEGIN:DAYLIGHT\r\n'
    'TZOFFSETFROM:+0100\r\n'
    'TZOFFSETTO:+0200\r\n'
    'TZNAME:CEST\r\n'
    'DTSTART:19700329T020000\r\n'
    'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\n'
    'END:DAYLIGHT\r\n'
    'BEGIN:STANDARD\r\n'
    'TZOFFSETFROM:+0200\r\n'
    'TZOFFSETTO:+0100\r\n'
    'TZNAME:CET\r\n'
    'DTSTART:19701025T030000\r\n'
    'RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\r\n'
    'END:STANDARD\r\n'
    'END:VTIMEZONE\r\n'
    'END:VCALENDAR\r\n'
)

# DAV capabilities announced in OPTIONS. '3' is required for Evolution and
# GNOME Online Accounts to use sync-collection (RFC 6578) instead of
# reloading the whole collection on every poll.
# 'extended-mkcol' is deliberately absent: we answer 405 to MKCOL, and
# advertising a capability we do not implement makes clients try it.
DAV_CAPABILITIES = '1, 3, calendar-access, addressbook'

XML_CONTENT_TYPE = 'application/xml; charset=utf-8'


# ── Authentication ───────────────────────────────────────────────────────


def _basic_auth():
    """Authenticate the Basic header against the configured databases.

    Returns ``None`` on success, a 401 when the credentials are wrong, or a
    503 when the database was too contended to tell (see below).
    """
    auth = request.httprequest.headers.get('Authorization', '')
    if not auth.startswith('Basic '):
        _logger.info('[DAV] no Basic auth header')
        return _unauthorized()
    try:
        decoded = base64.b64decode(auth[6:]).decode('utf-8')
        login, password = decoded.split(':', 1)
    except Exception:
        _logger.info('[DAV] could not decode auth header')
        return _unauthorized()

    credential = {'type': 'password', 'login': login, 'password': password}
    _detach_website_visitor_hook()
    for db_name in db.exp_list():
        try:
            auth_info = request.session.authenticate(db_name, credential)
        except Exception as exc:
            # A concurrent update is not a credential problem. Odoo's
            # ``session.authenticate`` updates ``res_users.login_date``, so
            # parallel DAV requests (DAVx5 opens several at once) collide on
            # the same row and PostgreSQL aborts the transaction with
            # "could not serialize access due to concurrent update".
            # Answering 401 makes the client believe the password is wrong —
            # it re-prompted and hammered the endpoint. Retry instead, and
            # if the retries are exhausted answer 503 so the client backs
            # off rather than dropping the credentials.
            if _is_retryable(exc):
                for attempt in range(AUTH_RETRIES):
                    time.sleep(AUTH_RETRY_DELAY * (attempt + 1))
                    # An aborted transaction poisons the cursor: every
                    # later statement fails with "current transaction is
                    # aborted" no matter what it is. Retrying without
                    # rolling back first can therefore never succeed, and
                    # the retry loop becomes three guaranteed failures.
                    try:
                        request.env.cr.rollback()
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        auth_info = request.session.authenticate(
                            db_name, credential)
                    except Exception as retry_exc:  # noqa: BLE001
                        exc = retry_exc
                        if not _is_retryable(retry_exc):
                            break
                        continue
                    else:
                        exc = None
                        break
                if exc is not None:
                    _logger.warning(
                        '[DAV] auth retryable failure db=%s after %d '
                        'attempts: %s', db_name, AUTH_RETRIES, exc)
                    return _unavailable()
            else:
                _logger.info('[DAV] auth failed db=%s: %s', db_name, exc)
                continue
        if auth_info.get('uid'):
            _logger.info('[DAV] auth ok login=%s db=%s uid=%s',
                         login, db_name, auth_info['uid'])
            return None
    _logger.info('[DAV] auth failed login=%s', login)
    return _unauthorized()


def _detach_website_visitor_hook():
    """Keep ``website``'s authenticate() override out of DAV requests.

    ``website/models/res_users.py:79`` calls
    ``website.visitor._get_visitor_from_request()`` before the credentials
    are checked, to merge an anonymous visitor into the logging-in user's
    one. That only makes sense for a browser: on a DAV request there is no
    session to merge, and the lookup raises, aborting the transaction so
    the whole request fails with 503.

    The override is a no-op when ``request.env.uid`` is falsy, so clearing
    the environment for the duration of the call keeps it out of the way.
    It is restored straight afterwards; nothing else in a DAV request
    relies on the pre-authentication environment.
    """
    try:
        request.env = api.Environment(request.env.cr, None, {})
    except Exception:  # noqa: BLE001
        pass


def _is_retryable(exc):
    """True when ``exc`` is a transient database conflict, not bad auth."""
    message = str(exc).lower()
    return ('could not serialize access' in message
            or 'deadlock detected' in message
            or 'concurrent update' in message
            # website.visitor hooks itself into every authenticate() call
            # (website/models/res_users.py:79). On a DAV request there is no
            # browser session, so the visitor lookup raises and aborts the
            # transaction before the credentials are even checked. The
            # transaction is recoverable by rolling back, so treat it as
            # transient rather than reporting a bad password.
            or 'current transaction is aborted' in message)


def _unavailable():
    """503 so the client retries instead of discarding its credentials."""
    return request.make_response(
        'CalDAV: temporarily unavailable, retry',
        headers=[('Retry-After', '2'),
                 ('Content-Type', 'text/plain; charset=utf-8')],
        status=503,
    )


def _unauthorized():
    return request.make_response(
        'CalDAV: Authorization required',
        headers=[('WWW-Authenticate', AUTH_HEADER),
                 ('Content-Type', 'text/plain; charset=utf-8')],
        status=401,
    )


def _options_response(allow='OPTIONS, GET, HEAD, PROPFIND, REPORT, PUT, DELETE'):
    return request.make_response(
        '',
        headers=[
            ('DAV', DAV_CAPABILITIES),
            ('Allow', allow),
            ('Content-Length', '0'),
        ],
    )


def _xml_response(body, status=207):
    return request.make_response(
        body,
        headers=[('Content-Type', XML_CONTENT_TYPE)],
        status=status,
    )


def _not_found():
    return request.make_response(
        'Not found', status=404,
        headers=[('Content-Type', 'text/plain; charset=utf-8')])


def _request_body():
    """The raw request body, whatever the client claimed its type is.

    Odoo's dispatcher calls ``request.httprequest.form`` before the
    controller runs, and werkzeug's form parser consumes the stream for
    ``application/x-www-form-urlencoded`` and ``multipart/form-data``.
    By the time we look, ``.data`` and ``get_data()`` are both empty and
    the raw stream is at EOF — which made a DAV REPORT sent by curl (whose
    default content type is form-urlencoded) look like an empty body and
    produce a 400.

    The body is therefore captured in ``_capture_body`` at the WSGI layer,
    before Odoo touches it, and stashed in ``environ``. This function only
    reads that copy, falling back to the normal paths for requests that
    did not go through the capture.
    """
    from ..hooks import BODY_ENVIRON_KEY
    environ = request.httprequest.environ
    captured = environ.get(BODY_ENVIRON_KEY)
    if captured:
        return captured
    httprequest = request.httprequest
    try:
        data = httprequest.get_data(cache=True)
        if data:
            return data
    except Exception:  # noqa: BLE001 - a broken stream is a client error
        pass
    stream = environ.get('wsgi.input')
    if stream is None:
        return b''
    try:
        return stream.read() or b''
    except Exception:  # noqa: BLE001
        return b''


def _bad_request(message='Malformed request body'):
    return request.make_response(
        message, status=400,
        headers=[('Content-Type', 'text/plain; charset=utf-8')])


# ── PROPFIND building blocks ─────────────────────────────────────────────


def _home_props(dav_type):
    """Properties of the principal / home-set resource."""
    href = xmlutil.escape(urls.root_url(dav_type) + '/')
    principal = xmlutil.escape(urls.principal_url(dav_type))
    # The home set is a plain collection; the principal is a separate
    # resource that points back at it. They must not share a URL — see
    # urls.principal_url().
    return (
        '<d:resourcetype><d:collection/></d:resourcetype>'
        '<d:displayname>%s</d:displayname>'
        '<d:current-user-principal><d:href>%s</d:href></d:current-user-principal>'
        '<d:principal-URL><d:href>%s</d:href></d:principal-URL>'
        '<cal:calendar-home-set><d:href>%s</d:href></cal:calendar-home-set>'
        '<card:addressbook-home-set><d:href>%s</d:href></card:addressbook-home-set>'
        '<d:current-user-privilege-set>'
        '<d:privilege><d:read/></d:privilege>'
        '<d:privilege><d:write/></d:privilege>'
        '<d:privilege><d:write-properties/></d:privilege>'
        '<d:privilege><d:write-content/></d:privilege>'
        '<d:privilege><d:bind/></d:privilege>'
        '<d:privilege><d:unbind/></d:privilege>'
        '</d:current-user-privilege-set>'
        % (xmlutil.escape(dav_type), principal, principal, href, href)
    )


def _scheduling_props(segment, props):
    """Properties of the scheduling inbox/outbox (RFC 6638 §2.2, §5.2)."""
    href = xmlutil.escape(urls.scheduling_url('calendar', segment))
    if segment == 'inbox':
        resourcetype = (
            '<d:resourcetype><d:collection/>'
            '<cal:schedule-inbox/></d:resourcetype>')
        extra = (
            '<cal:calendar-user-address-set>'
            '<d:href>%s</d:href>'
            '</cal:calendar-user-address-set>'
            % xmlutil.escape(
                'mailto:%s' % (request.env.user.partner_id.email
                               or request.env.user.email or '')))
    else:
        resourcetype = (
            '<d:resourcetype><d:collection/>'
            '<cal:schedule-outbox/></d:resourcetype>')
        extra = (
            '<cal:supported-calendar-data>'
            '<cal:calendar-data content-type="text/calendar" version="2.0"/>'
            '</cal:supported-calendar-data>'
            '<cal:supported-calendar-component-set>'
            '<cal:comp name="VEVENT"/>'
            '</cal:supported-calendar-component-set>')
    return (
        '%s'
        '<d:displayname>%s</d:displayname>'
        '<d:getcontenttype>httpd/unix-directory</d:getcontenttype>'
        '<d:current-user-principal><d:href>%s</d:href>'
        '</d:current-user-principal>'
        '%s'
        % (resourcetype,
           'Scheduling Inbox' if segment == 'inbox' else 'Scheduling Outbox',
           xmlutil.escape(urls.root_url('calendar') + '/'),
           extra)
    )


def _calendar_user_addresses(collection, user=None):
    """The addresses that identify this user in scheduling (RFC 6638 §2.1).

    ``calendar-user-address-set`` is how a client knows which ATTENDEE line
    is "me" when a REPLY arrives, and which address to put in ORGANIZER
    when it sends a REQUEST.

    ``user`` is passed in rather than read from ``request`` so the property
    builder stays callable outside a request (tests, scripts).
    """
    if user is None:
        # Fall back to the collection's owner, then to the request user.
        # ``request.env`` raises outside a request, so it is only touched
        # when there is genuinely nothing else to go on.
        user = collection.user_id
        if not user:
            user = request.env.user
    addresses = []
    email = user.partner_id.email or user.email
    if email:
        addresses.append('mailto:%s' % email)
    # The principal URL is a valid address type too, and clients that do
    # not use mailto fall back to it.
    addresses.append(urls.root_url(collection.dav_type) + '/')
    return addresses


def _collection_props(collection, user=None):
    """Properties of one collection (calendar or addressbook)."""
    href = xmlutil.escape(urls.collection_url(collection))
    home = xmlutil.escape(urls.root_url(collection.dav_type) + '/')
    if collection.dav_type == 'tasks':
        # Thunderbird hides a collection from its task view unless VTODO is
        # advertised here. It is the only component this collection serves.
        resourcetype = xmlutil.TASKS_RESOURCETYPE
        component_set = (
            '<cal:supported-calendar-component-set>'
            '<cal:comp name="VTODO"/>'
            '</cal:supported-calendar-component-set>'
        )
        extra = (
            '<cal:calendar-description>%s</cal:calendar-description>'
            '<A:calendar-color>%s</A:calendar-color>'
            '<A:calendar-order>%s</A:calendar-order>'
            '<cal:max-resource-size>10485760</cal:max-resource-size>'
            '<cal:supported-calendar-data>'
            '<cal:calendar-data content-type="text/calendar" '
            'version="2.0"/>'
            '</cal:supported-calendar-data>'
            '<cal:calendar-timezone>%s</cal:calendar-timezone>'
            % (xmlutil.escape(collection.name),
               xmlutil.escape(collection.client_property(
                   '{http://apple.com/ns/ical/}calendar-color')
                   or DEFAULT_CALENDAR_COLOR),
               collection.calendar_order or 0,
               xmlutil.escape(DEFAULT_TIMEZONE))
        )
    elif collection.dav_type == 'calendar':
        resourcetype = xmlutil.CALENDAR_RESOURCETYPE
        component_set = (
            '<cal:supported-calendar-component-set>'
            '<cal:comp name="VEVENT"/>'
            '</cal:supported-calendar-component-set>'
        )
        # RFC 6638 §2.1: a client cannot schedule anything without being
        # told where to POST it. The inbox is per user, the outbox per
        # collection, and calendar-user-address-set says which addresses
        # count as "us" when a REPLY comes back.
        addresses = _calendar_user_addresses(collection, user)
        address_set = ''.join(
            '<d:href>%s</d:href>' % xmlutil.escape(address)
            for address in addresses)
        extra = (
            '<cal:calendar-description>%s</cal:calendar-description>'
            '<A:calendar-color>%s</A:calendar-color>'
            '<A:calendar-order>%s</A:calendar-order>'
            '<cal:max-resource-size>10485760</cal:max-resource-size>'
            '<cal:supported-calendar-data>'
            '<cal:calendar-data content-type="text/calendar" '
            'version="2.0"/>'
            '</cal:supported-calendar-data>'
            '<cal:calendar-timezone>%s</cal:calendar-timezone>'
            '<cal:calendar-user-address-set>%s</cal:calendar-user-address-set>'
            '<cal:schedule-inbox-URL><d:href>%s</d:href>'
            '</cal:schedule-inbox-URL>'
            '<cal:schedule-outbox-URL><d:href>%s</d:href>'
            '</cal:schedule-outbox-URL>'
            '<cal:schedule-calendar-transp>'
            '<cal:%s/>'
            '</cal:schedule-calendar-transp>'
            % (xmlutil.escape(collection.name),
               xmlutil.escape(collection.client_property(
                   '{http://apple.com/ns/ical/}calendar-color')
                   or DEFAULT_CALENDAR_COLOR),
               collection.calendar_order or 0,
               xmlutil.escape(DEFAULT_TIMEZONE),
               address_set,
               xmlutil.escape(urls.scheduling_url('calendar', 'inbox')),
               xmlutil.escape(urls.scheduling_url('calendar', 'outbox')),
               'transparent' if collection.dav_type == 'calendar'
               else 'opaque')
        )
    else:
        resourcetype = xmlutil.ADDRESSBOOK_RESOURCETYPE
        component_set = ''
        extra = (
            '<card:addressbook-description>%s</card:addressbook-description>'
            '<card:max-resource-size>10485760</card:max-resource-size>'
            '<card:supported-address-data>'
            '<card:address-data-type content-type="text/vcard" '
            'version="3.0"/>'
            '</card:supported-address-data>'
            % xmlutil.escape(collection.name)
        )
    # The sync token has to be announced here, not only in the
    # sync-collection response. DAVx5 (and every other RFC 6578 client) reads
    # ``DAV:sync-token`` from the collection's PROPFIND first; without it the
    # client never stores a token and falls back to a full download on every
    # poll — which is what kept CardDAV from ever finishing its first sync.
    # ``cs:getctag`` is the legacy CalendarServer equivalent, still used by
    # older DAVx5 builds and by Apple's clients.
    sync_token = collection.sync_token()
    # Announce the reports this collection actually answers. A CardDAV
    # collection must advertise addressbook-query/addressbook-multiget;
    # announcing the CalDAV ones made clients probe for a calendar that is
    # not there.
    if collection.dav_type == 'calendar':
        report_set = (
            '<d:supported-report><d:report><cal:calendar-query/></d:report>'
            '</d:supported-report>'
            '<d:supported-report><d:report><cal:calendar-multiget/></d:report>'
            '</d:supported-report>'
            '<d:supported-report><d:report><d:sync-collection/></d:report>'
            '</d:supported-report>'
            '<d:supported-report><d:report><cal:free-busy-query/></d:report>'
            '</d:supported-report>'
            '<d:supported-report><d:report><d:expand-property/></d:report>'
            '</d:supported-report>'
        )
    else:
        report_set = (
            '<d:supported-report><d:report><card:addressbook-query/></d:report>'
            '</d:supported-report>'
            '<d:supported-report><d:report>'
            '<card:addressbook-multiget/></d:report></d:supported-report>'
            '<d:supported-report><d:report><d:sync-collection/></d:report>'
            '</d:supported-report>'
            '<d:supported-report><d:report><d:expand-property/></d:report>'
            '</d:supported-report>'
        )
    return (
        '<d:resourcetype>%s</d:resourcetype>'
        '<d:displayname>%s</d:displayname>'
        '<d:getcontenttype>httpd/unix-directory</d:getcontenttype>'
        '<d:owner><d:href>%s</d:href></d:owner>'
        '<d:current-user-principal><d:href>%s</d:href></d:current-user-principal>'
        '<cal:calendar-home-set><d:href>%s</d:href></cal:calendar-home-set>'
        '<card:addressbook-home-set><d:href>%s</d:href></card:addressbook-home-set>'
        '<d:sync-token>%s</d:sync-token>'
        '<cs:getctag>%s</cs:getctag>'
        '<d:current-user-privilege-set>'
        '<d:privilege><d:read/></d:privilege>'
        '<d:privilege><d:write/></d:privilege>'
        '<d:privilege><d:write-properties/></d:privilege>'
        '<d:privilege><d:write-content/></d:privilege>'
        '<d:privilege><d:bind/></d:privilege>'
        '<d:privilege><d:unbind/></d:privilege>'
        '</d:current-user-privilege-set>'
        '<d:supported-report-set>%s</d:supported-report-set>'
        '%s%s'
        % (resourcetype,
           xmlutil.escape(collection.display_name or collection.name),
           home, home, home, home,
           xmlutil.escape(sync_token), xmlutil.escape(sync_token),
           report_set, component_set, extra)
    )


#: Clark notation prefix -> the prefix we declare in every multistatus.
_CLARK_PREFIXES = {
    'DAV:': 'd',
    'urn:ietf:params:xml:ns:caldav': 'cal',
    'urn:ietf:params:xml:ns:carddav': 'card',
    'http://calendarserver.org/ns/': 'cs',
    'http://apple.com/ns/ical/': 'A',
}


def _dav_error(condition, description, status=403):
    """A DAV:error body (RFC 4918 §16) so clients can report *why*."""
    return request.make_response(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:error xmlns:d="DAV:"><d:%s/>'
        '<d:responsedescription>%s</d:responsedescription></d:error>'
        % (condition, xmlutil.escape(description)),
        headers=[('Content-Type', XML_CONTENT_TYPE)],
        status=status,
    )


def _clark_to_xml(name):
    """``{ns}local`` -> ``prefix:local`` for the namespaces we declare."""
    if not name.startswith('{'):
        return name
    namespace, _, local = name[1:].partition('}')
    prefix = _CLARK_PREFIXES.get(namespace)
    return '%s:%s' % (prefix, local) if prefix else local


def _prepare_task_values(collection, values, uid):
    """Turn parsed VTODO values into something ``project.task`` accepts.

    Two things a client sends have no direct field: CATEGORIES becomes
    ``tag_ids`` (records that may not exist yet) and the UID has to be the
    one in the URL, so a rename cannot fork the task. A task created by a
    client is personal — it belongs to the authenticated user and has no
    project, which is what Odoo's own to-do view shows.
    """
    values = dict(values)
    progress = values.pop('_progress', None)
    if progress is not None and 'progress' in collection._model()._fields:
        values['progress'] = progress
    categories = values.pop('_categories', None)
    if categories:
        tags = collection._model().env['project.tags']
        tag_ids = []
        for name in categories:
            name = (name or '').strip()
            if not name:
                continue
            tag = tags.search([('name', '=', name)], limit=1)
            if not tag:
                tag = tags.create({'name': name})
            tag_ids.append(tag.id)
        if tag_ids:
            values['tag_ids'] = [(6, 0, tag_ids)]

    if uid and collection.field_uuid:
        values[collection.field_uuid.name] = uid

    # A VTODO in this collection is a personal to-do by definition: the
    # collection's domain already restricts it to tasks without a project.
    values.setdefault('project_id', False)
    user = urls.user_for_request()
    if user:
        values.setdefault('user_ids', [(6, 0, [user.id])])

    return values


def _record_props(collection, record):
    """Properties of one event/contact resource (no body)."""
    return (
        '<d:resourcetype/>'
        '<d:getcontenttype>%s</d:getcontenttype>'
        '<d:getetag>%s</d:getetag>'
        % ('text/vcard' if collection.dav_type == 'addressbook'
           else 'text/calendar',
           xmlutil.escape(collection.record_etag(record)))
    )


def _record_body(collection, record):
    """Serialised .ics/.vcf for one record, or ``None`` on failure."""
    try:
        obj = collection.to_vobject(record)
        # A VTODO is built by icalendar and comes back as text; vobject
        # components (events, cards) need an explicit serialise call.
        if isinstance(obj, str):
            return obj
        return obj.serialize()
    except Exception as exc:
        _logger.warning('[DAV] could not serialise %s %s: %s',
                        collection.model_name, record.id, exc)
        return None


# ── Controller ───────────────────────────────────────────────────────────


class CalDAVController(http.Controller):

    # ── RFC 6764 discovery ───────────────────────────────────────────────
    #
    # Clients (GNOME Online Accounts, DAVx5, Thunderbird, Evolution) start
    # by GETting /.well-known/caldav WITHOUT a trailing slash. Both forms
    # are owned here for both protocols so discovery is unambiguous.
    #
    # 307, not 301: a PROPFIND that follows a 301 becomes a GET per RFC
    # 7231, and the client then reads the reply as an HTML page instead of
    # a multistatus.

    @http.route(
        ['/.well-known/caldav', '/.well-known/caldav/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'PROPFIND', 'OPTIONS', 'HEAD'],
        strict_slashes=False,
    )
    def well_known_caldav(self):
        _logger.info('[DAV] well-known caldav: %s -> /caldav/',
                     request.httprequest.method)
        return request.redirect('/caldav/', code=307, local=True)

    @http.route(
        ['/.well-known/carddav', '/.well-known/carddav/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'PROPFIND', 'OPTIONS', 'HEAD'],
        strict_slashes=False,
    )
    def well_known_carddav(self):
        _logger.info('[DAV] well-known carddav: %s -> /carddav/',
                     request.httprequest.method)
        return request.redirect('/carddav/', code=307, local=True)

    # NOTE: /.well-known/webdav is deliberately NOT owned here. It belongs
    # to dms_webdav, which redirects it to /webdav/ for file access. This
    # module used to claim both spellings and send them to /caldav/, which
    # made a DMS client's discovery land in the calendar — it got a window
    # that was not DMS at all. Only the two protocols this module actually
    # serves are announced.

    # ── Home sets ────────────────────────────────────────────────────────

    def _home_set(self, dav_type):
        """PROPFIND/GET on /caldav/ or /carddav/."""
        method = request.httprequest.method
        if method == 'OPTIONS':
            return _options_response()
        auth = _basic_auth()
        if auth:
            return auth

        user = urls.user_for_request()
        depth = request.httprequest.headers.get('Depth', '0')
        body = _request_body()

        if method == 'PROPFIND':
            props = xmlutil.requested_props(body)
            root_href = xmlutil.escape(urls.root_url(dav_type) + '/')
            responses = [
                xmlutil.response(root_href, _home_props(dav_type))
            ]
            if depth in ('1', 'infinity'):
                # A task collection is a calendar, so it is listed under
                # /caldav/ next to the event collections.
                types = (dav_type, 'tasks') if dav_type == 'calendar' \
                    else (dav_type,)
                listed = urls.collections_for(dav_type, user)
                for extra_type in types[1:]:
                    listed |= urls.collections_for(extra_type, user)
                for collection in listed:
                    responses.append(xmlutil.response(
                        xmlutil.escape(urls.collection_url(collection)),
                        _collection_props(collection)))
            return _xml_response(xmlutil.multistatus(responses))

        if method in ('GET', 'HEAD'):
            # Some clients GET the home set to check it exists. Answer with
            # a multistatus listing the collections rather than HTML.
            responses = [
                xmlutil.response(
                    xmlutil.escape(urls.root_url(dav_type) + '/'),
                    _home_props(dav_type))
            ]
            for collection in urls.collections_for(dav_type, user):
                responses.append(xmlutil.response(
                    xmlutil.escape(urls.collection_url(collection)),
                    _collection_props(collection)))
            return _xml_response(xmlutil.multistatus(responses))

        return _options_response()

    @http.route(
        ['/caldav', '/caldav/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT'],
        strict_slashes=False,
    )
    def caldav_home(self):
        return self._home_set('calendar')

    @http.route(
        ['/carddav', '/carddav/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT'],
        strict_slashes=False,
    )
    def carddav_home(self):
        return self._home_set('addressbook')

    @http.route(
        ['/caldav/principal', '/caldav/principal/',
         '/carddav/principal', '/carddav/principal/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS'],
        strict_slashes=False,
    )
    def dav_principal(self):
        """The principal resource (RFC 3744 §4).

        Declared before the collection routes so that ``principal`` is not
        mistaken for a collection slug.
        """
        if request.httprequest.method == 'OPTIONS':
            return _options_response()
        auth = _basic_auth()
        if auth:
            return auth
        dav_type = urls.split_path(request.httprequest.path)[0] or 'calendar'
        href = xmlutil.escape(urls.principal_url(dav_type))
        home = xmlutil.escape(urls.root_url(dav_type) + '/')
        email = request.env.user.partner_id.email or ''
        props = (
            '<d:resourcetype><d:principal/></d:resourcetype>'
            '<d:displayname>%s</d:displayname>'
            '<d:current-user-principal><d:href>%s</d:href></d:current-user-principal>'
            '<d:principal-URL><d:href>%s</d:href></d:principal-URL>'
            '<cal:calendar-home-set><d:href>%s</d:href></cal:calendar-home-set>'
            '<card:addressbook-home-set><d:href>%s</d:href></card:addressbook-home-set>'
            '<cal:calendar-user-address-set><d:href>mailto:%s</d:href>'
            '</cal:calendar-user-address-set>'
            % (xmlutil.escape(email or 'principal'), href, href, home, home,
               xmlutil.escape(email))
        )
        return _xml_response(xmlutil.multistatus([
            xmlutil.response(href, props)]))

    # ── Collection and record level ──────────────────────────────────────

    @http.route(
        ['/caldav/<string:slug>', '/caldav/<string:slug>/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT',
                 'PROPPATCH'],
        strict_slashes=False,
    )
    def caldav_collection(self, slug):
        return self._collection_dispatch('calendar', slug)

    # A task collection is a calendar whose component set is VTODO. It is
    # addressed by its slug like any other collection; the type lookup in
    # _collection_dispatch falls back to 'tasks' when no event collection
    # owns the slug, so /caldav/tasks/ resolves without a route of its own.

    @http.route(
        ['/carddav/<string:slug>', '/carddav/<string:slug>/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT',
                 'PROPPATCH'],
        strict_slashes=False,
    )
    def carddav_collection(self, slug):
        return self._collection_dispatch('addressbook', slug)

    def _collection_dispatch(self, dav_type, slug):
        method = request.httprequest.method
        # Read the body before anything else touches the request: Odoo
        # parses a form-encoded body eagerly, and once it has, the raw
        # stream is gone and a DAV REPORT looks empty.
        body = _request_body()
        if method == 'OPTIONS':
            return _options_response()
        auth = _basic_auth()
        if auth:
            return auth

        collection = urls.find_collection(dav_type, slug)
        if not collection and dav_type == 'calendar':
            # /caldav/<slug>/ serves both event and task collections: a
            # task collection is a calendar with a VTODO component set, so
            # it shares the root. Only the type differs.
            collection = urls.find_collection('tasks', slug)
        if not collection:
            _logger.info('[DAV] collection not found: %s/%s', dav_type, slug)
            return _not_found()

        user = urls.user_for_request()
        # Personal collections are invisible to anyone else.
        if collection.user_id and collection.user_id != user:
            _logger.info('[DAV] collection %s belongs to another user', slug)
            return _not_found()
        bound = urls.bind_user(collection, user)

        if method == 'PROPFIND':
            return self._propfind_collection(bound, user)
        if method == 'PROPPATCH':
            return self._proppatch_collection(bound)
        if method == 'REPORT':
            return self._report_collection(bound, user, body)
        if method in ('GET', 'HEAD'):
            return self._get_collection(bound, user)
        return _options_response()

    # ── RFC 6638 scheduling inbox / outbox ───────────────────────────────

    @http.route(
        ['/caldav/inbox', '/caldav/inbox/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT', 'POST'],
        strict_slashes=False,
    )
    def caldav_inbox(self):
        return self._scheduling_dispatch('inbox')

    @http.route(
        ['/caldav/outbox', '/caldav/outbox/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'POST'],
        strict_slashes=False,
    )
    def caldav_outbox(self):
        return self._scheduling_dispatch('outbox')

    def _scheduling_dispatch(self, segment):
        """The scheduling inbox and outbox (RFC 6638 §2.2, §5.2).

        The inbox is where another system delivers an invitation; the
        outbox is where a client hands us one to send. Both are POST
        endpoints — a GET on the outbox is meaningless and answered as an
        empty collection so a probing client does not treat it as broken.
        """
        method = request.httprequest.method
        if method == 'OPTIONS':
            return _options_response()
        auth = _basic_auth()
        if auth:
            return auth

        if method == 'POST':
            if segment == 'outbox':
                return self._outbox_post()
            return self._inbox_post()

        if method == 'PROPFIND':
            body = _request_body()
            props = xmlutil.requested_props(body)
            href = xmlutil.escape(
                urls.scheduling_url('calendar', segment))
            return _xml_response(xmlutil.multistatus([
                xmlutil.response(href, _scheduling_props(segment, props))
            ]))

        # GET/HEAD on the inbox lists what is waiting; on the outbox there
        # is nothing to list, so answer with an empty collection.
        return _xml_response(xmlutil.multistatus([
            xmlutil.response(
                xmlutil.escape(urls.scheduling_url('calendar', segment)),
                _scheduling_props(segment, None))
        ]))

    def _inbox_post(self):
        """An invitation delivered to us as an iTIP message."""
        body = _request_body()
        if not body:
            return _bad_request('Empty body')
        try:
            message = parse_itip(body)
        except ItipError as exc:
            _logger.info('[DAV] inbox POST rejected: %s', exc)
            return _dav_error('valid-calendar-data', str(exc))

        method = message['method']
        if method not in SUPPORTED_METHODS:
            return _dav_error(
                'supported-calendar-data',
                'iTIP method %s is not supported' % (method or 'none'))

        collection = self._default_calendar()
        if not collection:
            return _dav_error(
                'valid-calendar-data',
                'No calendar to deliver the invitation to.')

        if method == 'CANCEL':
            return self._itip_cancel(collection, message)
        if method == 'REPLY':
            return self._itip_reply(collection, message)
        return self._itip_request(collection, message)

    def _outbox_post(self):
        """A client hands us an iTIP message to send on its behalf.

        RFC 6638 §6.1: the server applies the message to the organiser's
        own calendar and delivers it. We do not relay mail here — the
        message is applied locally and the reply path (1b) does the
        mailing — but the request must succeed so the client does not
        retry forever.
        """
        body = _request_body()
        if not body:
            return _bad_request('Empty body')
        try:
            message = parse_itip(body)
        except ItipError as exc:
            _logger.info('[DAV] outbox POST rejected: %s', exc)
            return _dav_error('valid-calendar-data', str(exc))

        if message['method'] not in SUPPORTED_METHODS:
            return _dav_error(
                'supported-calendar-data',
                'iTIP method %s is not supported' % (message['method'] or 'none'))

        collection = self._default_calendar()
        if not collection:
            return _dav_error(
                'valid-calendar-data', 'No calendar to schedule from.')

        _logger.info('[DAV] outbox POST %s uid=%s',
                     message['method'], message['uid'])
        if message['method'] == 'REQUEST':
            response = self._itip_request(collection, message)
        elif message['method'] == 'REPLY':
            response = self._itip_reply(collection, message)
        else:
            response = self._itip_cancel(collection, message)
        # RFC 6638 §6.1: a successful scheduling POST answers 200 with the
        # recipient list, not 201 — nothing was created at the request URI.
        if response.status_code in (201, 204):
            return request.make_response(
                '<?xml version="1.0" encoding="utf-8"?>'
                '<C:schedule-response '
                'xmlns:C="urn:ietf:params:xml:ns:caldav">'
                '<C:response>'
                '<C:recipient><d:href xmlns:d="DAV:">%s</d:href></C:recipient>'
                '<C:request-status>2.0;Success</C:request-status>'
                '</C:response>'
                '</C:schedule-response>'
                % xmlutil.escape(message['uid']),
                headers=[('Content-Type', XML_CONTENT_TYPE)],
                status=200)
        return response

    def _default_calendar(self):
        """The calendar an invitation lands in when no collection is named."""
        user = urls.user_for_request()
        calendars = urls.collections_for('calendar', user)
        return calendars[:1] if calendars else False

    @http.route(
        ['/caldav', '/caldav/', '/carddav', '/carddav/',
         '/caldav/<string:slug>', '/caldav/<string:slug>/',
         '/carddav/<string:slug>', '/carddav/<string:slug>/'],
        type='http', auth='public', csrf=False,
        methods=['MKCOL'],
        strict_slashes=False,
    )
    def dav_mkcol_home(self, slug=None):
        return self._mkcol()

    @http.route(
        ['/caldav/<string:slug>', '/caldav/<string:slug>/',
         '/carddav/<string:slug>', '/carddav/<string:slug>/',
         '/caldav/<string:slug>/<string:filename>',
         '/carddav/<string:slug>/<string:filename>'],
        type='http', auth='public', csrf=False,
        methods=['LOCK', 'UNLOCK'],
        strict_slashes=False,
    )
    def dav_lock(self, slug, filename=None):
        """RFC 4918 §6: we advertise class 1 and 3, not 2.

        Class 2 means "supports locking". We do not, and we no longer claim
        to, so a compliant client will not send LOCK. If one does anyway,
        answer with a DAV error rather than 405 so it stops retrying.
        """
        auth = _basic_auth()
        if auth:
            return auth
        return _dav_error(
            'lock-token-submitted',
            'This server does not support locking (DAV class 2).',
            status=405)

    def _mkcol(self):
        """RFC 4918 §9.3: we do not create collections from a client.

        Collections are Odoo records with a domain and a model; a client
        cannot invent one. Answer 403 with a DAV error body so the client
        reports "server does not allow creating collections" instead of
        retrying a bare 405.
        """
        auth = _basic_auth()
        if auth:
            return auth
        _logger.info('[DAV] MKCOL %s: refused',
                     request.httprequest.path)
        return _dav_error(
            'cannot-modify-protected-property',
            'Collections are managed in Odoo; a client cannot create one.')

    def _proppatch_collection(self, collection):
        """Store the dead properties a client sets (RFC 4918 §9.2).

        Thunderbird writes ``calendar-color`` and ``calendar-order`` right
        after discovery; answering 405 made it log a failure and retry on
        every sync. A PROPPATCH is atomic: either every property is stored
        or none is, and the response reports a status per property.
        """
        body = _request_body()
        values = xmlutil.property_update_from_body(body)
        if not values:
            return _bad_request()
        _logger.info('[DAV] PROPPATCH %s: %s', collection.slug,
                     ', '.join(sorted(values)))
        collection.set_client_properties(values)
        # xmlutil.response() wraps its payload in one propstat, so the
        # properties go in as a flat list of empty elements.
        props = ''.join('<%s/>' % _clark_to_xml(name) for name in values)
        return _xml_response(xmlutil.multistatus([
            xmlutil.response(
                xmlutil.escape(urls.collection_url(collection)),
                props)]))

    def _propfind_collection(self, collection, user):
        depth = request.httprequest.headers.get('Depth', '0')
        body = _request_body()
        responses = [
            xmlutil.response(
                xmlutil.escape(urls.collection_url(collection)),
                _collection_props(collection))
        ]
        if depth in ('1', 'infinity'):
            records = collection.search_records()
            _logger.info('[DAV] PROPFIND %s depth=%s -> %d records',
                         collection.slug, depth, len(records))
            for record in records:
                responses.append(xmlutil.response(
                    xmlutil.escape(urls.record_url(collection, record)),
                    _record_props(collection, record)))
        return _xml_response(xmlutil.multistatus(responses))

    def _get_collection(self, collection, user):
        """GET on a collection returns the whole set as one .ics/.vcf."""
        records = collection.search_records()
        if collection.dav_type == 'calendar':
            parts = []
            for record in records:
                body = _record_body(collection, record)
                if not body:
                    continue
                # Strip the VCALENDAR wrapper: one wrapper for the whole set.
                inner = body.split('BEGIN:VEVENT', 1)
                if len(inner) == 2:
                    parts.append('BEGIN:VEVENT' + inner[1].split(
                        'END:VCALENDAR', 1)[0])
            payload = (
                'BEGIN:VCALENDAR\r\nVERSION:2.0\r\n'
                'PRODID:-//Vertel//Odoo CalDAV//EN\r\n'
                + ''.join(parts) + 'END:VCALENDAR\r\n'
            )
            content_type = 'text/calendar; charset=utf-8'
        else:
            payload = ''.join(
                _record_body(collection, record) or ''
                for record in records)
            content_type = 'text/vcard; charset=utf-8'
        return request.make_response(
            payload, headers=[('Content-Type', content_type)])

    def _report_collection(self, collection, user, body=None):
        if body is None:
            body = _request_body()
        report = xmlutil.body_root_name(body)
        _logger.info('[DAV] REPORT %s root=%s', collection.slug, report)

        if not report:
            return _bad_request()

        if report in ('calendar-multiget', 'addressbook-multiget'):
            return self._report_multiget(collection, body)
        if report == 'sync-collection':
            return self._report_sync(collection, body)
        if report in ('calendar-query', 'addressbook-query'):
            return self._report_query(collection, body)
        if report == 'free-busy-query':
            return self._report_free_busy(collection, body)
        if report == 'expand-property':
            return self._report_expand_property(collection, body)
        if report == 'principal-property-search':
            # Answer with the principal itself so a client that searches for
            # a user finds one instead of an empty multistatus.
            user = urls.user_for_request()
            href = xmlutil.escape(urls.root_url(collection.dav_type) + '/')
            return _xml_response(xmlutil.multistatus([
                xmlutil.response(href, _home_props(collection.dav_type))]))

        _logger.info('[DAV] unsupported report: %s', report)
        return _xml_response(xmlutil.multistatus([]), status=403)

    def _report_free_busy(self, collection, body):
        """RFC 4791 §7.10: answer with a VFREEBUSY of busy periods.

        Thunderbird asks for this when it shows an attendee's availability.
        We have no per-attendee free/busy data beyond the events the user can
        see, so the answer is built from this collection's own records —
        which is exactly what the collection's domain already scopes.
        """
        time_range = xmlutil.time_range_from_body(body)
        records = collection.search_records()
        if time_range:
            records = self._filter_time_range(records, time_range)
        start = (time_range or {}).get('start') or '19700101T000000Z'
        end = (time_range or {}).get('end') or '20380101T000000Z'
        periods = []
        for record in records:
            rec_start = getattr(record, 'start', None)
            if not rec_start:
                continue
            rec_stop = getattr(record, 'stop', None) or rec_start
            periods.append(
                'FREEBUSY;FBTYPE=BUSY:%s/%s'
                % (rec_start.strftime('%Y%m%dT%H%M%SZ'),
                   rec_stop.strftime('%Y%m%dT%H%M%SZ')))
        payload = (
            'BEGIN:VCALENDAR\r\n'
            'VERSION:2.0\r\n'
            'PRODID:-//Vertel//Odoo CalDAV//EN\r\n'
            'BEGIN:VFREEBUSY\r\n'
            'UID:%s\r\n'
            'DTSTAMP:%s\r\n'
            'DTSTART:%s\r\n'
            'DTEND:%s\r\n'
            '%s'
            'END:VFREEBUSY\r\n'
            'END:VCALENDAR\r\n'
            % (uuid.uuid4(),
               datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'),
               start, end,
               ''.join(period + '\r\n' for period in periods))
        )
        _logger.info('[DAV] free-busy %s -> %d periods',
                     collection.slug, len(periods))
        return request.make_response(
            payload,
            headers=[('Content-Type', 'text/calendar; charset=utf-8')])

    def _report_expand_property(self, collection, body):
        """RFC 3253 §3.8: return the requested properties, expanded.

        Clients use it to resolve ``calendar-home-set``/``addressbook-home-
        set`` in one round trip instead of a PROPFIND per level. Our home
        sets are plain hrefs, so expansion is the property itself.
        """
        return _xml_response(xmlutil.multistatus([
            xmlutil.response(
                xmlutil.escape(urls.collection_url(collection)),
                _collection_props(collection))]))

    def _report_multiget(self, collection, body):
        hrefs = xmlutil.hrefs_from_body(body)
        responses = []
        for href in hrefs:
            _dav_type, _slug, uid = urls.split_path(href)
            if not uid:
                responses.append(xmlutil.response(
                    xmlutil.escape(href), status='HTTP/1.1 404 Not Found'))
                continue
            record = collection.get_record(uid)
            if not record:
                responses.append(xmlutil.response(
                    xmlutil.escape(href), status='HTTP/1.1 404 Not Found'))
                continue
            payload = _record_body(collection, record)
            if payload is None:
                responses.append(xmlutil.response(
                    xmlutil.escape(href),
                    status='HTTP/1.1 500 Internal Server Error'))
                continue
            responses.append(xmlutil.response(
                xmlutil.escape(urls.record_url(collection, record)),
                _record_props(collection, record)
                + self._data_element(collection, payload)))
        return _xml_response(xmlutil.multistatus(responses))

    @staticmethod
    def _data_element(collection, payload):
        """Wrap a record body in the element the collection's type expects.

        RFC 6352 §10.4 gives address books ``card:address-data``; calendars
        use ``cal:calendar-data`` (RFC 4791 §9.6). A client that asks for
        address-data and gets calendar-data back sees a well-formed
        multistatus with no data in it, so it silently shows an empty
        address book — which is exactly what DAVx5, Thunderbird and GNOME
        Contacts all did.
        """
        if collection.dav_type == 'addressbook':
            tag = 'card:address-data'
        else:
            tag = 'cal:calendar-data'
        return '<%s>%s</%s>' % (tag, xmlutil.escape(payload), tag)

    def _report_sync(self, collection, body):
        old_token = xmlutil.sync_token_from_body(body)
        records = collection.search_records()
        changed, deleted = collection.sync_changes(old_token, records)
        _logger.info('[DAV] sync-collection %s token=%r -> %d changed',
                     collection.slug, old_token, len(changed))
        responses = []
        for record in changed:
            payload = _record_body(collection, record)
            if payload is None:
                continue
            responses.append(xmlutil.response(
                xmlutil.escape(urls.record_url(collection, record)),
                _record_props(collection, record)
                + self._data_element(collection, payload)))
        for uid in deleted:
            responses.append(xmlutil.response(
                xmlutil.escape('%s%s' % (
                    urls.collection_url(collection), uid)),
                status='HTTP/1.1 404 Not Found'))
        # The token goes last, after the responses, as RFC 6578 requires.
        document = xmlutil.multistatus(responses).replace(
            '</d:multistatus>',
            '<d:sync-token>%s</d:sync-token></d:multistatus>'
            % xmlutil.escape(collection.sync_token(records)))
        return _xml_response(document)

    def _report_query(self, collection, body):
        time_range = xmlutil.time_range_from_body(body)
        records = collection.search_records()
        if time_range:
            records = self._filter_time_range(records, time_range)
        if collection.dav_type == 'addressbook':
            records = self._filter_addressbook(records, body)
        _logger.info('[DAV] %s query %s -> %d records',
                     collection.dav_type,
                     'time-range' if time_range else 'all', len(records))
        responses = []
        for record in records:
            payload = _record_body(collection, record)
            if payload is None:
                continue
            responses.append(xmlutil.response(
                xmlutil.escape(urls.record_url(collection, record)),
                _record_props(collection, record)
                + self._data_element(collection, payload)))
        return _xml_response(xmlutil.multistatus(responses))

    def _filter_addressbook(self, records, body):
        """Apply the text-match filters of an addressbook-query.

        Matched against the same fields the vCard export uses, so a search
        for "anders" finds the contact whose FN contains it.
        """
        filters = xmlutil.addressbook_prop_filters(body)
        if not filters:
            return records

        def matches(record):
            name = (record.name or '').lower()
            email = ''
            if 'email' in record._fields and record.email:
                email = record.email.lower()
            for prop, value, match_type in filters:
                needle = value.lower()
                if prop in ('FN', 'N', 'NICKNAME'):
                    haystack = name
                elif prop == 'EMAIL':
                    haystack = email
                elif prop == 'ORG':
                    haystack = (record.parent_id.name or '').lower() \
                        if 'parent_id' in record._fields and record.parent_id \
                        else ''
                else:
                    # Unknown property: do not filter it out, the client may
                    # be asking for something we do not map.
                    continue
                found = (haystack == needle if match_type == 'equals'
                         else needle in haystack)
                if not found:
                    return False
            return True

        return records.filtered(matches)

    def _filter_time_range(self, records, time_range):
        """Keep records overlapping the requested window.

        Odoo already stores one row per occurrence of a recurring event, so
        a plain overlap test on start/stop is correct — no RRULE expansion
        is needed here.
        """
        from datetime import datetime

        def parse(value):
            if not value:
                return None
            try:
                return datetime.strptime(value, '%Y%m%dT%H%M%SZ')
            except ValueError:
                try:
                    return datetime.strptime(value, '%Y%m%d')
                except ValueError:
                    return None

        start = parse(time_range.get('start'))
        end = parse(time_range.get('end'))
        if not start and not end:
            return records

        def overlaps(record):
            rec_start = record.start
            rec_stop = record.stop or rec_start
            if rec_start is None:
                return False
            if end and rec_start >= end:
                return False
            if start and rec_stop and rec_stop <= start:
                return False
            return True

        return records.filtered(overlaps)

    # ── Single record: GET / PUT / DELETE ────────────────────────────────

    @http.route(
        ['/caldav/<string:slug>/<string:filename>',
         '/carddav/<string:slug>/<string:filename>'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS', 'PROPFIND',
                 'MOVE', 'COPY'],
        strict_slashes=False,
    )
    def dav_record(self, slug, filename):
        method = request.httprequest.method
        if method == 'OPTIONS':
            return _options_response()

        dav_type, _slug, uid = urls.split_path(request.httprequest.path)
        if not dav_type or not uid:
            return _not_found()

        auth = _basic_auth()
        if auth:
            return auth

        collection = urls.find_collection(dav_type, slug)
        if not collection and dav_type == 'calendar':
            # /caldav/<slug>/<file> serves task collections too: a task
            # collection is a calendar with a VTODO component set and shares
            # the root. Without this a PUT to /caldav/tasks/x.ics 404s even
            # though the collection itself resolves.
            collection = urls.find_collection('tasks', slug)
        if not collection:
            return _not_found()
        user = urls.user_for_request()
        if collection.user_id and collection.user_id != user:
            return _not_found()
        bound = urls.bind_user(collection, user)

        if method == 'PROPFIND':
            record = bound.get_record(uid)
            if not record:
                return _not_found()
            return _xml_response(xmlutil.multistatus([
                xmlutil.response(
                    xmlutil.escape(urls.record_url(bound, record)),
                    _record_props(bound, record))
            ]))

        if method in ('GET', 'HEAD'):
            record = bound.get_record(uid)
            if not record:
                _logger.info('[DAV] GET %s/%s: not found', slug, uid)
                return _not_found()
            payload = _record_body(bound, record)
            if payload is None:
                return request.make_response(
                    'Could not serialise record', status=500)
            headers = [
                ('Content-Type',
                 'text/calendar; charset=utf-8'
                 if dav_type == 'calendar'
                 else 'text/vcard; charset=utf-8'),
                ('ETag', bound.record_etag(record)),
            ]
            return request.make_response(payload, headers=headers)

        if method == 'PUT':
            return self._put_record(bound, uid)

        if method == 'DELETE':
            record = bound.get_record(uid)
            if not record:
                return _not_found()
            _logger.info('[DAV] DELETE %s/%s (id=%s)', slug, uid, record.id)
            record.sudo().unlink()
            # A deletion must move the sync token, otherwise a client that
            # polled once never learns the record is gone.
            bound.bump_sync_rev(removed=[uid])
            return request.make_response('', status=204)

        if method in ('MOVE', 'COPY'):
            # A record belongs to one collection by construction: the
            # collection's domain decides which records it contains, so
            # there is no second collection to move it into. Say so with a
            # DAV error instead of a bare 405, which clients report as a
            # protocol failure.
            _logger.info('[DAV] %s %s/%s: not supported', method, slug, uid)
            return _dav_error(
                'cannot-modify-protected-property',
                '%s is not supported: a record is selected by its '
                "collection's domain, it cannot be moved between "
                'collections.' % method)

        return _options_response()

    # ── iTIP (RFC 5546) ─────────────────────────────────────────────
    def _put_itip(self, collection, uid, body):
        """Apply an iTIP message delivered over CalDAV.

        Returns a response when the payload was an iTIP message we handled,
        or ``None`` when it should fall through to the generic PUT.
        """
        try:
            message = parse_itip(body)
        except ItipError as exc:
            _logger.info('[DAV] PUT %s/%s is not usable iTIP: %s',
                         collection.slug, uid, exc)
            return None

        method = message['method']
        if method not in SUPPORTED_METHODS:
            _logger.info('[DAV] PUT %s/%s: unsupported iTIP method %r',
                         collection.slug, uid, method)
            return _dav_error(
                'supported-calendar-data',
                'iTIP method %s is not supported' % (method or 'none'))

        if method == 'CANCEL':
            return self._itip_cancel(collection, message)
        if method == 'REPLY':
            return self._itip_reply(collection, message)
        if method == 'COUNTER':
            return self._itip_counter(collection, message)
        return self._itip_request(collection, message)

    def _itip_request(self, collection, message):
        """An invitation arrived: create or update the event for us."""
        event_model = collection._model()
        uid = message['uid']
        existing = event_model.sudo().search(
            [('uuid', '=', uid)], limit=1)

        # A stale invitation must not overwrite a newer one.
        if existing and message['sequence'] < (existing.itip_sequence or 0):
            _logger.info('[DAV] iTIP REQUEST %s seq %s < %s, ignored',
                         uid, message['sequence'], existing.itip_sequence)
            return request.make_response(
                '', headers=[('ETag', collection.record_etag(existing))],
                status=204)

        values = dict(message['event'])
        values['uuid'] = uid
        values['itip_sequence'] = message['sequence']

        organizer = message['organizer'] or {}
        organizer_email = organizer.get('email') or ''
        if organizer_email:
            owner = request.env['res.users'].sudo().search(
                [('partner_id.email', '=', organizer_email)], limit=1)
            if owner:
                # Organiser is one of ours: no external address needed.
                values['user_id'] = owner.id
                values['imip_organizer'] = False
            else:
                values['imip_organizer'] = organizer_email

        # A RECURRENCE-ID means "this one occurrence", not the series.
        # Odoo stores one row per occurrence, so the write has to land on
        # the row whose start matches — otherwise a single declined
        # instance would rewrite the whole series.
        recurrence_id = message['recurrence_id']
        target = existing
        if recurrence_id and existing:
            instance = event_model.sudo().search([
                ('recurrence_id', '=', existing.recurrence_id.id),
                ('start', '=', recurrence_id),
            ], limit=1) if existing.recurrence_id else event_model.browse()
            if instance:
                target = instance
                values.pop('uuid', None)
                values.pop('itip_sequence', None)

        if target:
            target.sudo().write(values)
            record = target
            status = 204
        else:
            record = event_model.sudo().create(values)
            status = 201

        self._sync_attendees(record, message['attendees'])
        return request.make_response(
            '', headers=[('ETag', collection.record_etag(record))],
            status=status)

    def _itip_reply(self, collection, message):
        """The organiser told us how an attendee responded."""
        event_model = collection._model()
        event = event_model.sudo().search(
            [('uuid', '=', message['uid'])], limit=1)
        if not event:
            return _dav_error('valid-calendar-data',
                              'No event with UID %s' % message['uid'])

        for attendee in message['attendees']:
            state = PARTSTAT_TO_STATE.get(attendee['partstat'])
            if not state:
                continue
            rows = event.attendee_ids.filtered(
                lambda a, e=attendee['email']: (a.email or '') == e)
            if rows:
                rows.sudo().write({'state': state})
        return request.make_response(
            '', headers=[('ETag', collection.record_etag(event))],
            status=204)

    def _itip_counter(self, collection, message):
        """A counter-proposal: someone asked for another time.

        Odoo has no counter-proposal state, so we do not move the event.
        Record the proposal on the event so the organiser can see it and
        answer by editing the meeting — silently dropping it would leave
        both sides waiting.
        """
        event_model = collection._model()
        event = event_model.sudo().search(
            [('uuid', '=', message['uid'])], limit=1)
        if not event:
            return _dav_error('valid-calendar-data',
                              'No event with UID %s' % message['uid'])

        proposed = message['event']
        start = proposed.get('start')
        stop = proposed.get('stop')
        event.sudo().message_post(
            body=(
                '<p><strong>Motförslag på ny tid</strong></p>'
                '<p>En deltagare har föreslagit en annan tid:</p>'
                '<ul><li>Från: %s</li><li>Till: %s</li></ul>'
                '<p>Händelsen är <em>inte</em> flyttad. Ändra tiden i '
                'kalendern om förslaget passar.</p>'
                % (start or '(saknas)', stop or '(saknas)')
            ),
            subtype_xmlid='mail.mt_note',
            message_type='notification',
        )
        return request.make_response(
            '', headers=[('ETag', collection.record_etag(event))],
            status=204)

    def _itip_cancel(self, collection, message):
        """A cancelled invitation: drop it from our calendar."""
        event_model = collection._model()
        event = event_model.sudo().search(
            [('uuid', '=', message['uid'])], limit=1)
        if not event:
            # Cancelling something we never had is not an error.
            return request.make_response('', status=204)

        if message['sequence'] < (event.itip_sequence or 0):
            return request.make_response('', status=204)

        event.sudo().unlink()
        return request.make_response('', status=204)

    def _sync_attendees(self, event, attendees):
        """Mirror the ATTENDEE lines onto calendar.attendee rows.

        Odoo keeps one row per attendee and the organiser replies against
        those rows, so they have to exist with the PARTSTAT we received.
        """
        Attendee = request.env['calendar.attendee'].sudo()
        Partner = request.env['res.partner'].sudo()
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

    def _put_record(self, collection, uid):
        """Create or replace one record from an .ics/.vcf body."""
        body = _request_body()
        if not body:
            return _bad_request('Empty body')
        _logger.info('[DAV] PUT %s/%s (%d bytes)',
                     collection.slug, uid, len(body))

        # An iTIP message is not a calendar object: it is an instruction
        # about one. Handle it before the generic parse, because a
        # METHOD:REQUEST with attendees needs attendee rows that the
        # generic field mapping knows nothing about.
        if collection.dav_type == 'calendar' and b'METHOD:' in body.upper():
            itip_response = self._put_itip(collection, uid, body)
            if itip_response is not None:
                return itip_response

        existing = collection.get_record(uid)
        try:
            values = collection.from_vobject(
                body.decode('utf-8', errors='replace'))
        except Exception as exc:
            _logger.warning('[DAV] PUT could not parse body: %s', exc)
            return _bad_request('Could not parse body: %s' % exc)

        if not values:
            return _bad_request('Body contained no usable component')

        if collection.dav_type == 'tasks':
            values = _prepare_task_values(collection, values, uid)

        model = collection._model()
        if existing:
            # Never let a client move a record out of its own collection:
            # the domain decided it was visible, so the write is allowed,
            # but the owner is not negotiable.
            existing.sudo().write(values)
            record = existing
            status = 204
        else:
            record = model.sudo().create(values)
            status = 201

        collection.bump_sync_rev(uids=[collection.record_uid(record)])

        return request.make_response(
            '',
            headers=[('ETag', collection.record_etag(record))],
            status=status,
        )
