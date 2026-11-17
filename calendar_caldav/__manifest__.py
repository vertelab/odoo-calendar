{
    "name": "Calendar CalDAV",
    "summary": "CalDAV support for Odoo Calendar",
    "version": "18.0.1.18.0",
    "category": "Calendar",
    "author": "Vertel Sverige AB",
    "website": "https://vertel.se/apps/odoo-calendar/calendar_caldav",
    "license": "AGPL-3",
    # The whole Radicale track is gone as of 2026-11-17. base_dav was dropped
    # 2026-10-25 (this module no longer reads dav.collection), and
    # personal_contact_carddav followed when res.ppartner moved into this
    # module — that dependency was the last link keeping contact_carddav ->
    # calendar_dav -> base_dav alive in every client install.
    #
    # base_dav imported radicale as a Python library, which on Python 3.12
    # raised a DeprecationWarning for importlib.abc.Traversable. Odoo logs
    # warnings with a traceback, so every odoo shell run looked like a crash.
    # Do not reintroduce any of those five modules here.
    "depends": ["calendar", "mail", "project"],
    "data": [
        "security/ir.model.access.csv",
        "data/caldav_collection_data.xml",
    ],
    "external_dependencies": {
        "python": ["icalendar", "vobject"],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "description": """
CalDAV endpoint for Odoo Calendar at /caldav/.

CalDAV clients (Thunderbird, iOS, etc.) connect using HTTP Basic Auth with
Odoo user credentials. Multi-database setups are supported.

== DNS SRV auto-discovery (RFC 6764) ==

To let CalDAV clients discover the calendar automatically (by entering only
an email address), add SRV records to the domain's DNS zone:

For HTTPS (recommended):
    _caldavs._tcp.example.com.  300  SRV  0 1 443  odoo.example.com.

For HTTP:
    _caldav._tcp.example.com.  300  SRV  0 1 80  odoo.example.com.

Replace example.com with your domain and odoo.example.com with the hostname
serving the CalDAV endpoint. The service must be reverse-proxied to the
Odoo server's /caldav/ URL.

== Well-known URI ==

The module also serves /.well-known/caldav/ (RFC 6764) which redirects to
/caldav/. Thunderbird, iOS and other clients use this for discovery.
    """,
}
