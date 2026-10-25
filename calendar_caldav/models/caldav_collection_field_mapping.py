# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Field mappings for CalDAV/CardDAV collections.

A mapping says: the iCalendar/vCard property ``SUMMARY`` is Odoo field
``name``. ``simple`` mappings use the type of the Odoo field to convert;
``code`` mappings run a small safe_eval snippet for the cases the type
cannot express (compound values such as ``N``, or computed strings).
"""
import base64
import datetime

import dateutil
import pytz
import vobject
from dateutil import tz

from odoo import api, fields, models, tools
from odoo.tools import safe_eval as safe_eval_module
from odoo.tools.safe_eval import safe_eval

# Odoo 18's safe_eval refuses raw modules. wrap_module() resolves every name
# eagerly with getattr(), so only names that actually exist in the installed
# vobject may be listed: vobject 0.9.9 has no ``vCalendar`` (calendars are
# built with ``iCalendar()``), and asking for it raises at import time and
# takes the whole registry down.
_VOBJECT_WHITELIST = [
    'vCard', 'iCalendar', 'readOne', 'readComponents',
]
vobject_safe = safe_eval_module.wrap_module(
    vobject, [name for name in _VOBJECT_WHITELIST if hasattr(vobject, name)],
)


class CaldavCollectionFieldMapping(models.Model):
    _name = 'caldav.collection.field_mapping'
    _description = 'CalDAV/CardDAV Field Mapping'
    _order = 'collection_id, sequence, name'

    collection_id = fields.Many2one(
        'caldav.collection', required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        required=True,
        help='Property name in the iCalendar/vCard object, e.g. SUMMARY, '
             'DTSTART, FN, EMAIL.',
    )
    mapping_type = fields.Selection(
        [('simple', 'Simple'), ('code', 'Code')],
        default='simple',
        required=True,
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
        help='Odoo field the property is mapped to.',
    )
    model_id = fields.Many2one(
        'ir.model',
        related='collection_id.model_id',
        ondelete='cascade',
    )
    import_code = fields.Text(
        help='Python code to build the Odoo value. Input: item (the vobject '
             'property). Output: result.',
    )
    export_code = fields.Text(
        help='Python code to build the property value. Input: record. '
             'Output: result.',
    )

    # ── Import (vCard/iCalendar → Odoo) ──────────────────────────────────

    def from_vobject(self, child):
        self.ensure_one()
        if self.mapping_type == 'code':
            return self._from_vobject_code(child)
        return self._from_vobject_simple(child)

    def _from_vobject_code(self, child):
        self.ensure_one()
        context = {
            'datetime': safe_eval_module.datetime,
            'dateutil': safe_eval_module.dateutil,
            'item': child,
            'result': None,
            'tz': safe_eval_module.dateutil.tz,
            'vobject': vobject_safe,
        }
        safe_eval(self.import_code or '', context, mode='exec', nocopy=True)
        return context.get('result')

    def _from_vobject_simple(self, child):
        self.ensure_one()
        name = self.name.lower()
        candidates = [
            '_from_vobject_%s_%s' % (self.field_id.ttype, name),
            '_from_vobject_%s' % self.field_id.ttype,
        ]
        for method_name in candidates:
            if hasattr(self, method_name):
                value = getattr(self, method_name)(child)
                if value:
                    return value
        return child.value

    @api.model
    def _from_vobject_datetime(self, item):
        value = item.value
        if isinstance(value, datetime.datetime):
            if value.tzinfo is not None:
                value = value.astimezone(pytz.UTC).replace(tzinfo=None)
            return value.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
        if isinstance(value, datetime.date):
            return value.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
        return None

    @api.model
    def _from_vobject_date(self, item):
        value = item.value
        if isinstance(value, datetime.datetime):
            if value.tzinfo is not None:
                value = value.astimezone(pytz.UTC).replace(tzinfo=None)
            return value.strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
        if isinstance(value, datetime.date):
            return value.strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
        return None

    @api.model
    def _from_vobject_binary(self, item):
        # vobject decodes PHOTO/LOGO with ENCODING=b to raw bytes; other
        # binary properties stay str. Odoo's Binary field expects the base64
        # payload as str, so normalise both cases to that.
        value = item.value
        if isinstance(value, bytes):
            return base64.b64encode(value).decode('ascii')
        return value

    @api.model
    def _from_vobject_char_n(self, item):
        return item.family

    # ── Export (Odoo → vCard/iCalendar) ──────────────────────────────────

    def to_vobject(self, record):
        self.ensure_one()
        if self.mapping_type == 'code':
            result = self._to_vobject_code(record)
        else:
            result = self._to_vobject_simple(record)
        if isinstance(result, datetime.datetime) and not result.tzinfo:
            return result.replace(tzinfo=tz.UTC)
        return result

    def _to_vobject_code(self, record):
        self.ensure_one()
        context = {
            'datetime': safe_eval_module.datetime,
            'dateutil': safe_eval_module.dateutil,
            'record': record,
            'result': None,
            'tz': safe_eval_module.dateutil.tz,
            'vobject': vobject_safe,
        }
        safe_eval(self.export_code or '', context, mode='exec', nocopy=True)
        return context.get('result')

    def _to_vobject_simple(self, record):
        self.ensure_one()
        candidates = [
            '_to_vobject_%s_%s' % (self.field_id.ttype, self.name.lower()),
            '_to_vobject_%s' % self.field_id.ttype,
        ]
        value = record[self.field_id.name]
        for method_name in candidates:
            if hasattr(self, method_name):
                return getattr(self, method_name)(value)
        return value

    @api.model
    def _to_vobject_datetime(self, value):
        result = fields.Datetime.from_string(value)
        return result.replace(tzinfo=tz.UTC)

    @api.model
    def _to_vobject_datetime_rev(self, value):
        return value and value.replace(
            '-', '').replace(' ', 'T').replace(':', '') + 'Z'

    @api.model
    def _to_vobject_date(self, value):
        return fields.Date.from_string(value)

    @api.model
    def _to_vobject_binary(self, value):
        # Odoo 18 returns Binary content as a base64 str (bytes only when the
        # value comes straight from the attachment cache). vobject wants str.
        if isinstance(value, bytes):
            return value.decode('ascii')
        return value or None

    @api.model
    def _to_vobject_char_n(self, value):
        return vobject.vcard.Name(family=value)
