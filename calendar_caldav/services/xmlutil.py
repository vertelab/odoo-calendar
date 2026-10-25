# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""XML helpers for the CalDAV/CardDAV endpoint.

The previous controller matched request bodies with regular expressions
(``re.findall(rb'<d:href>...')``). That breaks on every client that uses a
different namespace prefix — ``<D:href>``, ``<href>`` without a prefix, or
the default namespace — and it cannot read the ``time-range`` element at
all. Everything here parses properly and matches by *namespace URI*, never
by prefix, which is what RFC 4918 requires.
"""
import logging

from lxml import etree

_logger = logging.getLogger(__name__)

# Namespaces as (prefix, URI). The prefix is only used when serialising;
# parsing always matches on the URI.
NS_DAV = 'DAV:'
NS_CALDAV = 'urn:ietf:params:xml:ns:caldav'
NS_CARDDAV = 'urn:ietf:params:xml:ns:carddav'
NS_CS = 'http://calendarserver.org/ns/'
NS_APPLE = 'http://apple.com/ns/ical/'

NAMESPACES = {
    'd': NS_DAV,
    'cal': NS_CALDAV,
    'card': NS_CARDDAV,
    'cs': NS_CS,
    'A': NS_APPLE,
}

# Properties every client asks for in a PROPFIND. Answering them
# unconditionally is cheaper than tracking which ones were requested, and
# RFC 4918 allows a server to return more properties than asked for.
# NOTE: the *inner* content only. The caller wraps it in <d:resourcetype>,
# so including the tag here would nest it inside itself — which some
# clients reject as a malformed multistatus.
CALENDAR_RESOURCETYPE = '<d:collection/><cal:calendar/>'
ADDRESSBOOK_RESOURCETYPE = '<d:collection/><card:addressbook/>' 


def qname(namespace, tag):
    """Clark notation for an lxml element tag."""
    return '{%s}%s' % (namespace, tag)


def parse_body(data):
    """Parse a request body into an lxml element, or ``None``.

    A malformed body is a client error, not a server crash: return ``None``
    and let the caller answer 400.
    """
    if not data:
        return None
    try:
        # resolve_entities=False: a DAV body must never expand external
        # entities (XXE). The bodies are small and come from the network.
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, recover=False)
        return etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        _logger.info('[CalDAV] malformed XML body: %s', exc)
        return None


def body_root_name(data):
    """Local name of the body's root element, e.g. 'propfind'."""
    root = parse_body(data)
    if root is None:
        return None
    return etree.QName(root).localname


def requested_props(data):
    """Property names asked for in a PROPFIND body.

    Returns a set of ``(namespace, localname)`` tuples, or ``None`` when the
    body is an ``allprop`` request or absent (meaning: send everything).
    """
    root = parse_body(data)
    if root is None:
        return None
    if root.find(qname(NS_DAV, 'allprop')) is not None:
        return None
    prop = root.find(qname(NS_DAV, 'prop'))
    if prop is None:
        return None
    return {
        (etree.QName(child).namespace, etree.QName(child).localname)
        for child in prop
    }


def hrefs_from_body(data):
    """The ``<d:href>`` values of a multiget / calendar-multiget body."""
    root = parse_body(data)
    if root is None:
        return []
    return [
        (element.text or '').strip()
        for element in root.iter(qname(NS_DAV, 'href'))
        if (element.text or '').strip()
    ]


def sync_token_from_body(data):
    """The ``<d:sync-token>`` of a sync-collection body, or ''."""
    root = parse_body(data)
    if root is None:
        return ''
    element = root.find('.//' + qname(NS_DAV, 'sync-token'))
    if element is None or not element.text:
        return ''
    return element.text.strip()


def property_update_from_body(data):
    """The ``{clark-name: value}`` a PROPPATCH asks us to set.

    RFC 4918 §4.2: ``<d:propertyupdate>`` holds one or more ``<d:set>`` /
    ``<d:remove>`` blocks, each with a ``<d:prop>``. A value of ``None``
    means "remove this property". Only the first text child is kept, which
    is what every client we care about sends (colour, order, displayname).
    """
    root = parse_body(data)
    if root is None:
        return {}
    values = {}
    for block in root:
        tag = etree.QName(block).localname
        if tag not in ('set', 'remove'):
            continue
        for prop in block.iter(qname(NS_DAV, 'prop')):
            for element in prop:
                name = etree.QName(element).text
                if tag == 'remove':
                    values[name] = None
                else:
                    values[name] = (element.text or '').strip()
    return values


def time_range_from_body(data):
    """The ``<cal:time-range start=... end=...>`` of a calendar-query.

    Returns a dict with ``start``/``end`` as iCalendar UTC strings
    (``YYYYMMDDTHHMMSSZ``) or ``None`` for an open end. Returns ``None``
    when the body has no time-range at all.
    """
    root = parse_body(data)
    if root is None:
        return None
    element = root.find('.//' + qname(NS_CALDAV, 'time-range'))
    if element is None:
        return None
    return {
        'start': element.get('start') or None,
        'end': element.get('end') or None,
    }


def addressbook_prop_filters(data):
    """Text-match filters from an addressbook-query body.

    Returns a list of ``(property_name, value)`` where property_name is the
    vCard property the client wants matched (``FN``, ``EMAIL``, ``N``, ...).
    Only ``text-match`` with ``match-type="contains"`` is honoured — that is
    what Thunderbird and Evolution send when the user types in the search
    box. Everything else falls back to "return the whole addressbook",
    which is correct, just slower.
    """
    root = parse_body(data)
    if root is None:
        return []
    filters = []
    for prop_filter in root.iter(qname(NS_CARDDAV, 'prop-filter')):
        name = (prop_filter.get('name') or '').upper()
        if not name:
            continue
        match = prop_filter.find(qname(NS_CARDDAV, 'text-match'))
        if match is None:
            continue
        value = (match.text or '').strip()
        if not value:
            continue
        match_type = (match.get('match-type') or 'contains').lower()
        if match_type not in ('contains', 'equals'):
            continue
        filters.append((name, value, match_type))
    return filters


def multistatus(responses):
    """Wrap serialised ``<d:response>`` strings in a multistatus document."""
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<d:multistatus xmlns:d="DAV:" '
        'xmlns:cal="urn:ietf:params:xml:ns:caldav" '
        'xmlns:card="urn:ietf:params:xml:ns:carddav" '
        'xmlns:cs="http://calendarserver.org/ns/" '
        'xmlns:A="http://apple.com/ns/ical/">',
    ]
    parts.extend(responses)
    parts.append('</d:multistatus>')
    return '\n'.join(parts)


def propstat(prop_xml, status='HTTP/1.1 200 OK'):
    return (
        '<d:propstat><d:prop>%s</d:prop>'
        '<d:status>%s</d:status></d:propstat>' % (prop_xml, status)
    )


def response(href, prop_xml=None, status=None):
    """One ``<d:response>`` element.

    With ``prop_xml`` the response carries a propstat; with ``status`` it
    carries a bare status (404, 403, ...).
    """
    if prop_xml is not None:
        return '<d:response><d:href>%s</d:href>%s</d:response>' % (
            href, propstat(prop_xml))
    return '<d:response><d:href>%s</d:href><d:status>%s</d:status></d:response>' % (
        href, status)


def escape(value):
    """XML-escape a text value (``None`` becomes '')."""
    if value is None:
        return ''
    return (
        str(value)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )
