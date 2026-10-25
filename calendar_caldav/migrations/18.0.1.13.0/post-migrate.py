"""Seed the sync log with the records that already exist.

The sync counter only advances on writes the module sees, so records that
predate it were never logged. A client that synced once held a token
claiming to know the collection, and was told "nothing changed" forever
after — its address book stayed empty while the server reported success.
"""

import json

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Collection = env['caldav.collection']
    for collection in Collection.search([]):
        try:
            records = collection.search_records()
        except Exception:  # noqa: BLE001
            continue
        uids = [collection.record_uid(record) for record in records]
        # Stamp the records with the revision we are about to publish. A
        # client holding any older token then sees them as changes; marking
        # them with an older revision would hide them from exactly the
        # clients that need them.
        new_rev = (collection.sync_rev or 0) + 1
        log = {str(uid): new_rev for uid in uids if uid}
        collection.write({
            'sync_rev': new_rev,
            'sync_rev_log': json.dumps(log),
        })
