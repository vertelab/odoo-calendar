import base64
import logging

from odoo import http, models
SessionExpiredException = http.SessionExpiredException
from odoo.service import db

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _auth_method_user(cls):
        request = http.request
        uid = request.env.uid
        if uid is not None and uid not in cls._get_public_users():
            return

        auth = request.httprequest.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            raise SessionExpiredException("Session expired")

        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            login, password = decoded.split(":", 1)
        except Exception:
            raise SessionExpiredException("Invalid Basic Auth")

        credential = {"type": "password", "login": login, "password": password}

        for db_name in db.exp_list():
            try:
                auth_info = request.session.authenticate(db_name, credential)
                if auth_info.get("uid"):
                    return
            except Exception:
                continue

        raise SessionExpiredException("Authentication failed")
