# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Adopt res.ppartner's ir.model.data rows from personal_contact_carddav.

res.ppartner moved into calendar_caldav on 2026-11-17 when the Radicale track
(contact_carddav -> calendar_dav -> base_dav) was retired.

The model itself needs no data migration: res.ppartner is a *model*, not a
table owned by a module, so the res_ppartner table keeps its rows when
_name moves. Verified on 2026-11-17: aanstoot has 0 rows, ledningssystem has
5, and neither database has a single ir.model.data row for res.ppartner.

This script therefore does nothing in those databases. It exists because a
database created before the move could have ir.model.data rows under
personal_contact_carddav (e.g. from a module upgrade that recorded the model
xmlid). Without adoption the record would point at a module that is about to
be uninstalled, and Odoo would delete the res_id it references.

Idempotent: skips when there is nothing to adopt, and skips when the target
xmlid already exists.
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY_MODULE = "personal_contact_carddav"
TARGET_MODULE = "calendar_caldav"
MODEL = "res.ppartner"


def migrate(cr, version):
    if not version:
        # Fresh install: the model is created by this module, nothing to adopt.
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Imd = env["ir.model.data"].sudo()

    legacy = Imd.search([
        ("module", "=", LEGACY_MODULE),
        ("model", "=", MODEL),
    ])
    if not legacy:
        _logger.info(
            "calendar_caldav 18.0.1.18.0: no %s ir.model.data rows under %s "
            "- nothing to adopt.", MODEL, LEGACY_MODULE,
        )
        return

    adopted = 0
    for row in legacy:
        already = Imd.search([
            ("module", "=", TARGET_MODULE),
            ("name", "=", row.name),
            ("model", "=", MODEL),
        ], limit=1)
        if already:
            # Target exists: drop the legacy row rather than leave a dangling
            # reference to a module that is being uninstalled.
            _logger.info(
                "calendar_caldav 18.0.1.18.0: %s already owned by %s, "
                "removing legacy row %s/%s.",
                row.name, TARGET_MODULE, LEGACY_MODULE, row.name,
            )
            row.unlink()
            continue
        row.write({"module": TARGET_MODULE})
        adopted += 1
        _logger.info(
            "calendar_caldav 18.0.1.18.0: adopted %s from %s (res_id %s).",
            row.name, LEGACY_MODULE, row.res_id,
        )

    _logger.info(
        "calendar_caldav 18.0.1.18.0: adopted %d %s xmlid(s) from %s.",
        adopted, MODEL, LEGACY_MODULE,
    )
