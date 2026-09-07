{
    "name": "Calendar CalDAV",
    "summary": "CalDAV support for Odoo Calendar",
    "version": "18.0.1.0.0",
    "category": "Calendar",
    "author": "Vertel Sverige AB",
    "license": "AGPL-3",
    "depends": ["calendar"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "test": [
        "tests/test_caldav.py",
    ],
    "external_dependencies": {
        "python": ["icalendar"],
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
