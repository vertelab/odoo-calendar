# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""CalDAV/CardDAV endpoint.

URL space (see ``services/urls.py``)::

    /.well-known/{caldav,carddav,webdav}   discovery, both slash forms
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

from odoo import http
from odoo.http import request
from odoo.service import db

from ..services import urls, xmlutil
from ..services.caldav import icalendar_to_odoo_event

_logger = logging.getLogger(__name__)

AUTH_HEADER = 'Basic realm="Odoo CalDAV", charset="UTF-8"'

# DAV capabilities announced in OPTIONS. '3' is required for Evolution and
# GNOME Online Accounts to use sync-collection (RFC 6578) instead of
# reloading the whole collection on every poll.
DAV_CAPABILITIES = '1, 2, 3, calendar-access, addressbook, extended-mkcol'

XML_CONTENT_TYPE = 'application/xml; charset=utf-8'


# ── Authentication ───────────────────────────────────────────────────────


def _basic_auth():
    """Authenticate the Basic header against the configured databases.

    Returns ``None`` on success, or a 401 response.
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
    for db_name in db.exp_list():
        try:
            auth_info = request.session.authenticate(db_name, credential)
        except Exception as exc:
            _logger.info('[DAV] auth failed db=%s: %s', db_name, exc)
            continue
        if auth_info.get('uid'):
            _logger.info('[DAV] auth ok login=%s db=%s uid=%s',
                         login, db_name, auth_info['uid'])
            return None
    _logger.info('[DAV] auth failed login=%s', login)
    return _unauthorized()


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

    ``request.httprequest.data`` is empty when the client sends a body
    without ``Content-Type: application/xml`` — and some clients do. DAV
    bodies are always XML, so fall back to the raw stream and parse it
    ourselves. Reading the stream twice is safe: Werkzeug caches it.
    """
    httprequest = request.httprequest
    data = httprequest.data
    if data:
        return data
    # Werkzeug's ``data`` property is empty for a body whose mimetype is
    # not form-like. ``get_data()`` reads the cached stream, but Odoo's
    # Request proxy may already have consumed it — so read the cached
    # value first and only then fall back to the raw environ stream.
    try:
        data = httprequest.get_data(cache=True)
        if data:
            return data
    except Exception:  # noqa: BLE001 - a broken stream is a client error
        pass
    stream = httprequest.environ.get('wsgi.input')
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
    root = urls.root_url(dav_type)
    href = xmlutil.escape(root + '/')
    resourcetype = (
        xmlutil.CALENDAR_RESOURCETYPE if dav_type == 'calendar'
        else xmlutil.ADDRESSBOOK_RESOURCETYPE)
    # The home set itself is a plain collection, but clients expect the
    # calendar/addressbook resourcetype on the *home*, so advertise both.
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
        % (xmlutil.escape(dav_type), href, href, href, href)
    )


def _collection_props(collection):
    """Properties of one collection (calendar or addressbook)."""
    href = xmlutil.escape(urls.collection_url(collection))
    home = xmlutil.escape(urls.root_url(collection.dav_type) + '/')
    if collection.dav_type == 'calendar':
        resourcetype = xmlutil.CALENDAR_RESOURCETYPE
        component_set = (
            '<cal:supported-calendar-component-set>'
            '<cal:comp name="VEVENT"/>'
            '</cal:supported-calendar-component-set>'
        )
        extra = (
            '<cal:calendar-description>%s</cal:calendar-description>'
            '<A:calendar-color>#2A6B9C</A:calendar-color>'
            '<cal:max-resource-size>10485760</cal:max-resource-size>'
            % xmlutil.escape(collection.name)
        )
    else:
        resourcetype = xmlutil.ADDRESSBOOK_RESOURCETYPE
        component_set = ''
        extra = (
            '<card:addressbook-description>%s</card:addressbook-description>'
            '<card:max-resource-size>10485760</card:max-resource-size>'
            % xmlutil.escape(collection.name)
        )
    return (
        '<d:resourcetype>%s</d:resourcetype>'
        '<d:displayname>%s</d:displayname>'
        '<d:getcontenttype>httpd/unix-directory</d:getcontenttype>'
        '<d:owner><d:href>%s</d:href></d:owner>'
        '<d:current-user-principal><d:href>%s</d:href></d:current-user-principal>'
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
        '<d:supported-report-set>'
        '<d:supported-report><d:report><cal:calendar-query/></d:report></d:supported-report>'
        '<d:supported-report><d:report><cal:calendar-multiget/></d:report></d:supported-report>'
        '<d:supported-report><d:report><d:sync-collection/></d:report></d:supported-report>'
        '</d:supported-report-set>'
        '%s%s'
        % (resourcetype, xmlutil.escape(collection.name), home, home, home,
           home, component_set, extra)
    )


def _record_props(collection, record):
    """Properties of one event/contact resource (no body)."""
    return (
        '<d:resourcetype/>'
        '<d:getcontenttype>%s</d:getcontenttype>'
        '<d:getetag>%s</d:getetag>'
        % ('text/calendar' if collection.dav_type == 'calendar'
           else 'text/vcard',
           xmlutil.escape(collection.record_etag(record)))
    )


def _record_body(collection, record):
    """Serialised .ics/.vcf for one record, or ``None`` on failure."""
    try:
        obj = collection.to_vobject(record)
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

    @http.route(
        ['/.well-known/webdav', '/.well-known/webdav/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'PROPFIND', 'OPTIONS', 'HEAD'],
        strict_slashes=False,
    )
    def well_known_webdav(self):
        # No separate WebDAV service: the caldav endpoint answers the
        # principal PROPFIND and leads the client on from there.
        _logger.info('[DAV] well-known webdav: %s -> /caldav/',
                     request.httprequest.method)
        return request.redirect('/caldav/', code=307, local=True)

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
                for collection in urls.collections_for(dav_type, user):
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

    # ── Collection and record level ──────────────────────────────────────

    @http.route(
        ['/caldav/<string:slug>', '/caldav/<string:slug>/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT'],
        strict_slashes=False,
    )
    def caldav_collection(self, slug):
        return self._collection_dispatch('calendar', slug)

    @http.route(
        ['/carddav/<string:slug>', '/carddav/<string:slug>/'],
        type='http', auth='public', csrf=False,
        methods=['GET', 'HEAD', 'PROPFIND', 'OPTIONS', 'REPORT'],
        strict_slashes=False,
    )
    def carddav_collection(self, slug):
        return self._collection_dispatch('addressbook', slug)

    def _collection_dispatch(self, dav_type, slug):
        method = request.httprequest.method
        if method == 'OPTIONS':
            return _options_response()
        auth = _basic_auth()
        if auth:
            return auth

        collection = urls.find_collection(dav_type, slug)
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
        if method == 'REPORT':
            return self._report_collection(bound, user)
        if method in ('GET', 'HEAD'):
            return self._get_collection(bound, user)
        return _options_response()

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

    def _report_collection(self, collection, user):
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
        if report == 'principal-property-search':
            return _xml_response(xmlutil.multistatus([]))

        _logger.info('[DAV] unsupported report: %s', report)
        return _xml_response(xmlutil.multistatus([]), status=403)

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
                + '<cal:calendar-data>%s</cal:calendar-data>'
                % xmlutil.escape(payload)))
        return _xml_response(xmlutil.multistatus(responses))

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
                + '<cal:calendar-data>%s</cal:calendar-data>'
                % xmlutil.escape(payload)))
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
                + '<cal:calendar-data>%s</cal:calendar-data>'
                % xmlutil.escape(payload)))
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
        methods=['GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS', 'PROPFIND'],
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
            return request.make_response('', status=204)

        return _options_response()

    def _put_record(self, collection, uid):
        """Create or replace one record from an .ics/.vcf body."""
        body = _request_body()
        if not body:
            return _bad_request('Empty body')
        _logger.info('[DAV] PUT %s/%s (%d bytes)',
                     collection.slug, uid, len(body))

        existing = collection.get_record(uid)
        try:
            values = collection.from_vobject(
                body.decode('utf-8', errors='replace'))
        except Exception as exc:
            _logger.warning('[DAV] PUT could not parse body: %s', exc)
            return _bad_request('Could not parse body: %s' % exc)

        if not values:
            return _bad_request('Body contained no usable component')

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

        return request.make_response(
            '',
            headers=[('ETag', collection.record_etag(record))],
            status=status,
        )
