# Copyright 2022 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Calendar dav",
    "summary": "Extension of the base_dav module to work better with the calendar",
    'version': '18.0.1.1.0',
    "category": "Calendar",
    "website": "https://vertel.se/apps/odoo-calendar/calendar_dav",
    "author": "Vertel Sverige AB, initOS GmbH, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    # ------------------------------------------------------------------
    # INSTALLABLE: True — 2026-10-15
    #
    # Spärren 2026-09-22 togs bort sedan den visat sig bygga på en felaktig
    # premiss. Konflikten gäller ENDAST den exakta sökvägen /.well-known/caldav
    # (utan avslutande slash):
    #
    #   /.well-known/caldav/   (med slash)    -> calendar_caldav  307 -> /caldav/
    #   /.well-known/caldav    (utan slash)   -> base_dav        301 -> /.dav
    #
    # DAV-klienter (DAVx5, Thunderbird, iOS) använder formen MED slash, som
    # fortfarande går till calendar_caldav. Båda routes samexisterar.
    #
    # Detta spår (base_dav -> calendar_dav -> contact_carddav) behövs för
    # CardDAV (/.dav). Kalendern fortsätter gå via calendar_caldav.
    #
    # Verifierat i drift 2026-10-15:
    #   /.well-known/caldav/  -> 307 -> /caldav/        (calendar_caldav)
    #   /.well-known/carddav  -> 301 -> /.dav           (base_dav)
    #   PROPFIND /.dav/       -> 207                    (base_dav/Radicale)
    #
        # Retired 2026-10-25: the Radicale-based DAV track is superseded by
    # calendar_caldav, which is the single CalDAV+CardDAV server for
    # ledningssystem. Both tracks registered /.well-known/caldav, and
    # whichever answered first won — the Radicale track answered and
    # returned an empty 207 for every client (DAVx5, Thunderbird,
    # Evolution). The routes are unregistered in the code, not here:
    # installable=False also stops Odoo from loading the module's
    # models, which broke res.ppartner and caldav.collection.
    'installable': True,
    # code stays available for reference and data migration.
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "depends": [
        "base_dav",
        "calendar",
    ],
}
