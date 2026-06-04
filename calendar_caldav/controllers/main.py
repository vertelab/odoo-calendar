import base64
import logging
from html import escape

from odoo import http
from odoo.http import request
from odoo.service import db
from ..services.caldav import odoo_event_to_icalendar, odoo_events_to_icalendar, icalendar_to_odoo_event

_logger = logging.getLogger(__name__)

AUTH_HEADER = 'Basic realm="Odoo CalDAV", charset="UTF-8"'


def _basic_auth():
    auth = request.httprequest.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        _logger.info("_basic_auth: no Basic auth header")
        return _unauthorized()
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        login, password = decoded.split(":", 1)
    except Exception:
        _logger.info("_basic_auth: failed to decode auth header")
        return _unauthorized()
    _logger.info("_basic_auth: trying login=%s across %s databases", login, db.exp_list())
    credential = {"type": "password", "login": login, "password": password}
    for db_name in db.exp_list():
        try:
            auth_info = request.session.authenticate(db_name, credential)
            if auth_info.get("uid"):
                _logger.info("_basic_auth: success login=%s db=%s uid=%s", login, db_name, auth_info["uid"])
                return
        except Exception as e:
            _logger.info("_basic_auth: failed db=%s: %s", db_name, e)
    _logger.info("_basic_auth: auth failed login=%s", login)
    return _unauthorized()


def _unauthorized():
    return request.make_response(
        "CalDAV: Authorization required",
        headers=[("WWW-Authenticate", AUTH_HEADER), ("Content-Type", "text/plain; charset=utf-8")],
        status=401,
    )


def _options_response():
    return request.make_response(
        "",
        headers=[
            ("DAV", "1, 2, calendar-access"),
            ("Allow", "OPTIONS, GET, HEAD, PROPFIND, REPORT, PUT"),
            ("Content-Length", "0"),
        ],
    )


def _event_href(base_url, event):
    return f"{escape(base_url)}/caldav/events/{event.id}.ics"


def _calendar_prop_xml(base_url, display_name):
    return (
        '<d:prop>'
        f'<d:displayname>{escape(display_name)}</d:displayname>'
        '<d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>'
        f'<cal:calendar-description>{escape(display_name)} calendar</cal:calendar-description>'
        '<A:calendar-color>#2A6B9C</A:calendar-color>'
        '<d:getcontenttype>httpd/unix-directory</d:getcontenttype>'
        f'<d:owner><d:href>{escape(base_url)}/caldav/</d:href></d:owner>'
        f'<d:current-user-principal><d:href>{escape(base_url)}/caldav/</d:href></d:current-user-principal>'
        f'<cal:calendar-home-set><d:href>{escape(base_url)}/caldav/</d:href></cal:calendar-home-set>'
        '<d:current-user-privilege-set>'
        '<d:privilege><d:read/></d:privilege>'
        '<d:privilege><d:write/></d:privilege>'
        '<d:privilege><d:write-properties/></d:privilege>'
        '<d:privilege><d:write-content/></d:privilege>'
        '<d:privilege><d:unlock/></d:privilege>'
        '<d:privilege><d:bind/></d:privilege>'
        '<d:privilege><d:unbind/></d:privilege>'
        '</d:current-user-privilege-set>'
        '</d:prop>'
    )


def _propfind_caldav(base_url, events, display_name):
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:A="http://apple.com/ns/ical/">',
        '<d:response>',
        f'<d:href>{escape(base_url)}/caldav/</d:href>',
        '<d:propstat>',
        _calendar_prop_xml(base_url, display_name),
        '<d:status>HTTP/1.1 200 OK</d:status>',
        '</d:propstat>',
        '</d:response>',
    ]
    for event in events:
        href = _event_href(base_url, event)
        parts.append('<d:response>')
        parts.append(f'<d:href>{href}</d:href>')
        parts.append('<d:propstat>')
        parts.append('<d:prop>')
        parts.append(f'<d:displayname>{escape(event.name)}</d:displayname>')
        parts.append('<d:resourcetype/>')
        parts.append('<d:getcontenttype>text/calendar</d:getcontenttype>')
        etag = str(event.dav_last_modified) if event.dav_last_modified else ""
        parts.append(f'<d:getetag>"{escape(etag)}"</d:getetag>')
        parts.append('</d:prop>')
        parts.append('<d:status>HTTP/1.1 200 OK</d:status>')
        parts.append('</d:propstat>')
        parts.append('</d:response>')
    parts.append('</d:multistatus>')
    return "\n".join(parts)


def _find_event(event_id_or_uuid):
    try:
        eid = int(event_id_or_uuid)
        return request.env["calendar.event"].browse(eid).exists()
    except (ValueError, TypeError):
        return request.env["calendar.event"]


class CalDAVController(http.Controller):

    @http.route(
        "/.well-known/caldav/",
        type="http",
        auth="public",
        csrf=False,
        methods=["GET", "PROPFIND", "OPTIONS"],
        strict_slashes=False,
    )
    def well_known_discovery(self):
        _logger.info("[CalDAV] well-known: %s -> 307 to /caldav/", request.httprequest.method)
        base_url = request.httprequest.url_root.rstrip("/")
        return request.redirect(f"{base_url}/caldav/", code=307)

    @http.route([
        "/caldav/events/<string:event_uuid>.ics",
        "/caldav/<string:event_uuid>.ics",
    ], type="http", auth="public", csrf=False, methods=["GET"])
    def get_event(self, event_uuid):
        _logger.info("[CalDAV] GET event: uuid=%s", event_uuid)
        auth_result = _basic_auth()
        if auth_result:
            return auth_result
        event = _find_event(event_uuid)
        if not event:
            _logger.info("[CalDAV] GET event: not found uuid=%s", event_uuid)
            return request.not_found()
        base_url = request.httprequest.url_root.rstrip("/")
        ical = odoo_event_to_icalendar(event, base_url=base_url)
        last_modified = event.dav_last_modified
        last_modified_str = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT") if last_modified else ""
        etag = str(last_modified) if last_modified else ""
        return request.make_response(
            ical.to_ical(),
            headers=[
                ("Content-Type", "text/calendar"),
                ("ETag", f'"{etag}"'),
                ("Last-Modified", last_modified_str),
            ],
        )

    @http.route([
        "/caldav/events/<string:event_uuid>.ics",
        "/caldav/<string:event_uuid>.ics",
    ], type="http", auth="public", csrf=False, methods=["PUT"])
    def update_event(self, event_uuid):
        _logger.info("[CalDAV] PUT event: uuid=%s", event_uuid)
        auth_result = _basic_auth()
        if auth_result:
            return auth_result
        ical_str = request.httprequest.data.decode("utf-8")
        event = _find_event(event_uuid)
        if not event:
            _logger.info("[CalDAV] PUT event: not found uuid=%s, creating new", event_uuid)
            event = icalendar_to_odoo_event(ical_str)
        else:
            event = icalendar_to_odoo_event(ical_str, event)
        etag = str(event.dav_last_modified) if event.dav_last_modified else ""
        return request.make_response("", headers=[("ETag", f'"{etag}"')])

    @http.route("/caldav/", type="http", auth="public", csrf=False, strict_slashes=False)
    def caldav_dispatch(self):
        method = request.httprequest.method
        _logger.info("[CalDAV] dispatch: method=%s", method)

        if method == "OPTIONS":
            _logger.info("[CalDAV] OPTIONS (no auth required)")
            return _options_response()

        if method == "HEAD":
            auth_result = _basic_auth()
            if auth_result:
                return auth_result
            return request.make_response("", headers=[("Content-Type", "text/html; charset=utf-8")])

        if method == "GET":
            auth_result = _basic_auth()
            if auth_result:
                return auth_result
            cal_name = request.env.user.partner_id.name
            base_url = request.httprequest.url_root.rstrip("/")
            events = request.env["calendar.event"].search([])
            ical = odoo_events_to_icalendar(events, cal_name=cal_name, base_url=base_url)
            return request.make_response(
                ical.to_ical(),
                headers=[("Content-Type", "text/calendar")],
            )

        if method == "PROPFIND":
            auth_result = _basic_auth()
            if auth_result:
                return auth_result
            depth = request.httprequest.headers.get("Depth", "0")
            body = request.httprequest.data
            if body:
                _logger.info("[CalDAV] PROPFIND body (first 500): %s", body.decode("utf-8", errors="replace")[:500])
            _logger.info("[CalDAV] PROPFIND depth=%s", depth)
            cal_name = request.env.user.partner_id.name
            events = request.env["calendar.event"].search([]) if depth in ("1", "infinity") else []
            base_url = request.httprequest.url_root.rstrip("/")
            xml = _propfind_caldav(base_url, events, cal_name)
            _logger.info("[CalDAV] PROPFIND depth=%s -> %d events", depth, len(events))
            return request.make_response(xml, headers=[("Content-Type", "application/xml; charset=utf-8")])

        if method == "REPORT":
            auth_result = _basic_auth()
            if auth_result:
                return auth_result
            base_url = request.httprequest.url_root.rstrip("/")
            body = request.httprequest.data or b""
            _logger.info("[CalDAV] REPORT body (first 500): %s", body.decode("utf-8", errors="replace")[:500])

            if b"calendar-multiget" in body:
                import re
                hrefs = re.findall(rb'<d:href>([^<]+)</d:href>', body)
                parts = [
                    '<?xml version="1.0" encoding="utf-8"?>',
                    '<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">',
                ]
                for href_bytes in hrefs:
                    href = href_bytes.decode("utf-8")
                    m = re.search(r'/caldav/events/(\d+)\.ics', href)
                    if not m:
                        parts.append(f'<d:response><d:href>{escape(href)}</d:href><d:status>HTTP/1.1 404 Not Found</d:status></d:response>')
                        continue
                    event = request.env["calendar.event"].browse(int(m.group(1))).exists()
                    if not event:
                        parts.append(f'<d:response><d:href>{escape(href)}</d:href><d:status>HTTP/1.1 404 Not Found</d:status></d:response>')
                        continue
                    ical = odoo_event_to_icalendar(event, base_url=base_url)
                    etag = str(event.dav_last_modified) if event.dav_last_modified else ""
                    parts.append('<d:response>')
                    parts.append(f'<d:href>{escape(href)}</d:href>')
                    parts.append('<d:propstat>')
                    parts.append('<d:prop>')
                    parts.append(f'<d:getetag>"{escape(etag)}"</d:getetag>')
                    parts.append(f'<cal:calendar-data>{escape(ical.to_ical().decode("utf-8"))}</cal:calendar-data>')
                    parts.append('</d:prop>')
                    parts.append('<d:status>HTTP/1.1 200 OK</d:status>')
                    parts.append('</d:propstat>')
                    parts.append('</d:response>')
                parts.append('</d:multistatus>')
                return request.make_response(
                    "\n".join(parts),
                    headers=[("Content-Type", "application/xml; charset=utf-8")],
                )

            _logger.info("[CalDAV] REPORT (sync): returning all events")
            events = request.env["calendar.event"].search([])
            parts = [
                '<?xml version="1.0" encoding="utf-8"?>',
                '<d:multistatus xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/">',
            ]
            for event in events:
                href = _event_href(base_url, event)
                etag = str(event.dav_last_modified) if event.dav_last_modified else ""
                parts.append('<d:response>')
                parts.append(f'<d:href>{href}</d:href>')
                parts.append('<d:propstat>')
                parts.append('<d:prop>')
                parts.append(f'<d:getetag>"{escape(etag)}"</d:getetag>')
                parts.append('</d:prop>')
                parts.append('<d:status>HTTP/1.1 200 OK</d:status>')
                parts.append('</d:propstat>')
                parts.append('</d:response>')
            parts.append('</d:multistatus>')
            return request.make_response(
                "\n".join(parts),
                headers=[("Content-Type", "application/xml; charset=utf-8")],
            )

        if method == "PUT":
            auth_result = _basic_auth()
            if auth_result:
                return auth_result
            body = request.httprequest.data or b""
            _logger.info("[CalDAV] PUT on /caldav/ - body (%d bytes): %s", len(body), body.decode("utf-8", errors="replace"))
            try:
                from icalendar import Calendar as ICal
                cal = ICal.from_ical(body)
                last_etag = ""
                for component in cal.walk():
                    if component.name != "VEVENT":
                        continue
                    event_uid = str(component.get("uid", ""))
                    event_name = str(component.get("summary", ""))
                    start = component.get("dtstart")
                    start_dt = start.dt if start else None
                    if not event_uid and not event_name:
                        continue
                    event = request.env["calendar.event"].browse()
                    if event_uid:
                        matches = event.search([("uuid", "=", event_uid)])
                        if len(matches) == 1:
                            event = matches
                        elif len(matches) > 1 and event_name:
                            narrow = matches.filtered(lambda e: e.name == event_name)
                            if len(narrow) == 1:
                                event = narrow
                            elif len(narrow) > 1 and start_dt:
                                narrow = narrow.filtered(lambda e: e.start == start_dt)
                                if narrow:
                                    event = narrow[:1]
                    if not event and event_name:
                        event = event.search([("name", "=", event_name)], limit=1)
                    if not event and event_uid:
                        try:
                            from uuid import UUID as UuidLib
                            event = request.env["calendar.event"].browse(UuidLib(event_uid).int).exists()
                        except Exception:
                            pass
                    ical_str = ICal()
                    ical_str.add("prodid", "-//Odoo Calendar//EN")
                    ical_str.add("version", "2.0")
                    ical_str.add_component(component)
                    ical_str = ical_str.to_ical().decode("utf-8")
                    if not event:
                        _logger.info("[CalDAV] PUT on /caldav/ -> creating new event (uid=%s, name=%s)", event_uid, event_name)
                        event = icalendar_to_odoo_event(ical_str)
                    else:
                        event = icalendar_to_odoo_event(ical_str, event)
                    last_modified = event.dav_last_modified
                    last_etag = str(last_modified) if last_modified else ""
                    _logger.info("[CalDAV] PUT on /caldav/ -> processed event id=%s (uid=%s)", event.id, event_uid)
                return request.make_response(
                    "",
                    headers=[("ETag", f'"{last_etag}"')],
                )
            except Exception as e:
                _logger.info("[CalDAV] PUT on /caldav/ -> error: %s", e)
                import traceback
                _logger.info(traceback.format_exc())
            return request.make_response("Calendar update not supported via this URL", status=405)

        _logger.info("[CalDAV] unsupported method=%s", method)
        return request.not_found()
