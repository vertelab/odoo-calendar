# Copyright 2022 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Calendar dav",
    "summary": "Extension of the base_dav module to work better with the calendar",
    "version": "0.1",
    "category": "Calendar",
    "website": "https://github.com/OCA/calendar",
    "author": "Vertel Sverige AB, initOS GmbH, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    # ------------------------------------------------------------------
    # INSTALLABLE: False — 2026-09-22
    #
    # Detta är OCA-sparet (base_dav -> calendar_dav -> contact_carddav)
    # som bygger pa Radicale. Vertel har ett EGET, fristaende CalDAV-spar:
    # calendar_caldav (controllers/main.py + services/caldav.py, endpoint
    # /caldav/). Bada registrerar /.well-known/caldav och kolliderar.
    #
    # Beslut 2026-09-22: calendar_caldav ar standard. Se README
    # "CalDAV: val av spar". Skal:
    #   - calendar_caldav: DAV: 1, 2, calendar-access; RFC 6764-discovery;
    #     HTTP Basic Auth mot Odoo (multi-DB); GET/PUT/PROPFIND fungerar.
    #   - base_dav-sparet: 500 pa rot-PROPFIND
    #     (collection.py:113, odoo_collection=None), 403 pa collections.
    #
    # installable=False -> Odoo satter state='uninstallable' och vagrar
    # bade installera och auto-installera modulen (db.py:54,90).
    # Ta bort denna sparr ENDAST om base_dav-sparet repareras och valjs.
    # ------------------------------------------------------------------
    "installable": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "depends": [
        "base_dav",
        "calendar",
    ],
}
