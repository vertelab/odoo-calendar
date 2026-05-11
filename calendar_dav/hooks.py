# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from uuid import uuid4

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Sätter unika UUID:n för kalenderhändelser vid installation.
    I Odoo 18 skickas 'env' direkt till hooken.
    """
    _logger.info("Setting unique UUID for calendar events")
    
    # Vi söker efter alla event. 
    # Om du har extremt mycket data kan .search([]) begränsas.
    events = env["calendar.event"].search([("uuid", "=", False)])
    
    if not events:
        return

    _logger.info("Updating %s events...", len(events))

    for event in events:
        # Vi använder 'write' direkt på recordsetet i loopen 
        # eller tilldelning. Odoo 18 hanterar cache effektivt.
        event.uuid = str(uuid4())
