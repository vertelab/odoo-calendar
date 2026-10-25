# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Collections for the CalDAV/CardDAV endpoint.

A collection is one calendar or one addressbook as the client sees it: a
name, a model, a domain that selects the records, and a field mapping that
translates between Odoo fields and iCalendar/vCard properties.

This is deliberately a *separate* model from ``dav.collection`` (the OCA /
Radicale track). ``dav.collection`` is built around Radicale's ``Item``
objects and its storage API (``dav_list``/``dav_get``/``dav_upload``) — it
cannot be used without Radicale, and inheriting it would keep the whole
Radicale track alive. ``caldav.collection`` only depends on ``vobject``.

Two rules that the Radicale track got wrong and that are load-bearing here:

1. **The domain is evaluated as the authenticated user.** ``dav.collection``
   switched to SUPERUSER *before* evaluating the domain, so ``user`` in
   ``[('partner_ids','in',user.partner_id.id)]`` was OdooBot and every
   calendar came back empty. Here the domain is evaluated first, and only
   then is the search executed with elevated rights (needed because the
   record rules are written for the UI, not for a CalDAV sync).

2. **Privacy is enforced in the domain, not by record rules.** In Odoo 18
   ``calendar_event_rule_private`` only covers write/create/unlink; reads
   are unrestricted for ``base.group_user``. A CalDAV endpoint that just
   searched the domain would hand out other people's private events.
"""
import logging
import re

from dateutil import tz

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Collection types. 'files' from dav.collection is intentionally absent:
# this endpoint serves CalDAV and CardDAV only.
DAV_TYPE_SELECTION = [
    ('calendar', 'Calendar'),
    ('addressbook', 'Addressbook'),
]


class CaldavCollection(models.Model):
    _name = 'caldav.collection'
    _description = 'CalDAV/CardDAV Collection'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    slug = fields.Char(
        compute='_compute_slug',
        store=True,
        readonly=False,
        index=True,
        help='URL segment, e.g. "work" in /caldav/work/. Derived from the '
             'name; must be unique per type because it addresses exactly one '
             'collection.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    dav_type = fields.Selection(
        DAV_TYPE_SELECTION,
        string='Type',
        required=True,
        default='calendar',
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        domain=[('transient', '=', False)],
        ondelete='cascade',
    )
    model_name = fields.Char(related='model_id.model', store=True)
    domain = fields.Char(
        required=True,
        default='[]',
        help='Record selector, evaluated as the authenticated user. '
             'Use "user" for the current user, e.g. '
             "[('partner_ids', 'in', user.partner_id.id)].",
    )
    field_uuid = fields.Many2one(
        'ir.model.fields',
        string='UID field',
        domain="[('model_id', '=', model_id), "
               "('ttype', 'in', ('char', 'text'))]",
        help='Field holding the stable UID used in the .ics/.vcf file name. '
             'Leave empty to use the database id.',
    )
    field_write_date = fields.Many2one(
        'ir.model.fields',
        string='Revision field',
        domain="[('model_id', '=', model_id), "
               "('ttype', 'in', ('datetime', 'char'))]",
        help='Field used as the REV / ETag source. Defaults to write_date.',
    )
    field_mapping_ids = fields.One2many(
        'caldav.collection.field_mapping',
        'collection_id',
        string='Field mappings',
    )
    component = fields.Char(
        compute='_compute_component',
        help='iCalendar/vCard component this collection serves.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        index=True,
        ondelete='cascade',
        help='Leave empty for a collection shared by all users. Set it for '
             'a personal collection (e.g. "Personal Contacts").',
    )

    _sql_constraints = [
        ('name_type_uniq', 'unique(name, dav_type, user_id)',
         'A collection with this name and type already exists.'),
        ('slug_type_uniq', 'unique(slug, dav_type)',
         'The URL slug must be unique per collection type.'),
    ]

    @api.depends('name')
    def _compute_slug(self):
        """Derive a URL-safe slug from the name.

        Nothing clever: lowercase, non-alphanumerics collapsed to a dash.
        The slug is stored and editable because changing it breaks every
        client that cached the old URL.
        """
        for collection in self:
            if collection.slug:
                continue
            source = (collection.name or '').lower()
            source = source.replace('å', 'a').replace('ä', 'a')
            source = source.replace('ö', 'o').replace('ø', 'o')
            slug = re.sub(r'[^a-z0-9]+', '-', source).strip('-')
            collection.slug = slug or 'collection'

    @api.depends('dav_type')
    def _compute_component(self):
        for collection in self:
            collection.component = (
                'VCALENDAR' if collection.dav_type == 'calendar'
                else 'VCARD'
            )

    @api.constrains('domain')
    def _check_domain(self):
        for collection in self:
            try:
                collection._eval_domain()
            except Exception as error:
                raise ValidationError(
                    'Invalid domain on collection %(name)s: %(error)s',
                    name=collection.name, error=error,
                ) from error

    @api.constrains('model_id', 'field_uuid', 'field_write_date',
                    'field_mapping_ids')
    def _check_fields_belong_to_model(self):
        for collection in self:
            for field in (collection.field_uuid,
                          collection.field_write_date):
                if field and field.model_id != collection.model_id:
                    raise ValidationError(
                        'Field %(field)s does not belong to model '
                        '%(model)s (collection %(name)s).',
                        field=field.name,
                        model=collection.model_id.model,
                        name=collection.name,
                    )
            for mapping in collection.field_mapping_ids:
                if mapping.field_id.model_id != collection.model_id:
                    raise ValidationError(
                        'Mapped field %(field)s does not belong to model '
                        '%(model)s (collection %(name)s).',
                        field=mapping.field_id.name,
                        model=collection.model_id.model,
                        name=collection.name,
                    )

    # ── Domain evaluation ────────────────────────────────────────────────

    @api.model
    def _eval_context(self):
        """Context for safe_eval of ``domain``.

        Runs as the *authenticated* user. Callers must not pre-switch to
        SUPERUSER — that is exactly the bug this model exists to avoid.

        ``self.env.user`` is not enough on its own: the ORM hands the model
        a sudo-ed environment in several paths, and ``env.user`` then reads
        as OdooBot (id 1, partner 2). The domain is evaluated here, in the
        model, so the caller's uid has to be passed in explicitly — see
        ``with_user_context``.
        """
        return {'user': self._eval_user()}

    @api.model
    def _eval_user(self):
        """The user the domain is evaluated for.

        ``self.env.context['caldav_user_id']`` wins when set (the controller
        sets it from the authenticated request); otherwise ``env.user``.
        """
        uid = self.env.context.get('caldav_user_id')
        if uid:
            return self.env['res.users'].sudo().browse(uid)
        return self.env.user

    @api.model
    def with_user_context(self, user):
        """Return this recordset bound to ``user`` for domain evaluation."""
        return self.with_context(caldav_user_id=user.id)

    def _eval_domain(self):
        self.ensure_one()
        return list(safe_eval(self.domain or '[]', self._eval_context()))

    def _privacy_domain(self):
        """Extra selector that keeps private events private.

        Odoo 18's ``calendar_event_rule_private`` only guards write access;
        reads are open to every internal user. Without this clause a CalDAV
        sync would expose other people's private events in clear text.
        """
        self.ensure_one()
        if self.model_name != 'calendar.event':
            return []
        user = self._eval_user()
        partner = user.partner_id.id
        return [
            '|', ('privacy', '!=', 'private'),
            '|', ('user_id', '=', user.id),
            ('partner_ids', 'in', partner),
        ]

    def _search_domain(self):
        """Full selector: the configured domain plus the privacy guard."""
        self.ensure_one()
        domain = self._eval_domain()
        privacy = self._privacy_domain()
        if not privacy:
            return domain
        if not domain:
            return privacy
        return ['&'] + domain + privacy

    # ── Record access ────────────────────────────────────────────────────

    def _model(self):
        self.ensure_one()
        return self.env[self.model_name]

    def search_records(self):
        """Records visible in this collection, for the authenticated user.

        The domain is evaluated as the user (so ``user`` is correct), then
        the search runs with elevated rights because the UI record rules
        would otherwise hide records the user legitimately syncs (e.g. an
        event owned by a colleague that the user is an attendee of).
        Privacy is enforced in the domain instead — see ``_privacy_domain``.
        """
        self.ensure_one()
        domain = self._search_domain()
        return self._model().sudo().search(domain)

    def get_record(self, uid):
        """Single record by UID (or database id when no UID field is set)."""
        self.ensure_one()
        if not uid:
            return self._model().browse()
        if self.field_uuid:
            domain = [(self.field_uuid.name, '=', uid)]
        else:
            try:
                domain = [('id', '=', int(uid))]
            except (TypeError, ValueError):
                return self._model().browse()
        # Keep the collection selector so a UID from another collection (or
        # another user's personal collection) cannot be read here.
        domain = ['&'] + domain + self._search_domain()
        return self._model().sudo().search(domain, limit=1)

    def record_uid(self, record):
        """The UID this collection uses for ``record``.

        Odoo stores a recurring event as one row per occurrence, and every
        row inherits the same ``uuid`` from the master. A UID must identify
        one resource, so occurrences get the master UID plus their start
        time — the same convention iCalendar uses for RECURRENCE-ID. Without
        this, five recurring series produced 353 rows sharing five UIDs, and
        clients saw one event per series (ledningssystem 2026-10-25).
        """
        self.ensure_one()
        base = None
        if self.field_uuid:
            base = record[self.field_uuid.name]
        if not base:
            base = str(record.id)
        if 'recurrence_id' in record._fields and record.recurrence_id:
            stamp = record.start.strftime('%Y%m%dT%H%M%SZ') if record.start \
                else str(record.id)
            return '%s-%s' % (base, stamp)
        return base

    def record_rev(self, record):
        """Revision string (REV / ETag source) for ``record``."""
        self.ensure_one()
        if self.field_write_date:
            value = record[self.field_write_date.name]
        elif 'write_date' in record._fields:
            value = record.write_date
        else:
            value = None
        if not value:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime('%Y%m%dT%H%M%SZ')
        return str(value).replace('-', '').replace(':', '').replace(' ', 'T')

    def record_etag(self, record):
        """Strong ETag for ``record`` (quoted, as HTTP requires)."""
        self.ensure_one()
        return '"%s-%s"' % (self.record_uid(record), self.record_rev(record))

    # ── Sync token (RFC 6578) ────────────────────────────────────────────

    def sync_token(self, records=None):
        """A token that changes whenever the collection's content changes.

        RFC 6578 wants an opaque token; clients only compare it. Deriving it
        from the newest revision in the collection (plus the record count)
        means a token can be recomputed at any time without storing state,
        and a deleted record still moves the token because the count drops.

        Without a working token clients fall back to downloading everything
        on every poll — which is what the Radicale track did, and why
        DAVx5 hammered the endpoint every 30 minutes.
        """
        self.ensure_one()
        if records is None:
            records = self.search_records()
        newest = ''
        for record in records:
            rev = self.record_rev(record)
            if rev > newest:
                newest = rev
        return 'http://vertel.se/ns/sync/%s/%s-%s' % (
            self.slug or self.id, len(records), newest or 'empty')

    def sync_changes(self, old_token, records=None):
        """Records changed since ``old_token``.

        Returns ``(changed, deleted_uids)``. A token this server did not
        issue (or one from before a purge) is answered with the full set and
        ``deleted_uids`` empty: RFC 6578 allows the server to fall back to a
        full resync, and it is the only safe answer when history is gone.
        """
        self.ensure_one()
        if records is None:
            records = self.search_records()
        current = self.sync_token(records)
        if not old_token or old_token == current:
            return ([] if old_token else records, [])

        # Token format: .../<slug>/<count>-<newest_rev>
        try:
            tail = old_token.rsplit('/', 1)[1]
            _count, _, old_newest = tail.partition('-')
        except (IndexError, ValueError):
            return records, []

        changed = records.filtered(
            lambda r: self.record_rev(r) > old_newest)
        # Deletions cannot be reconstructed from a stateless token: the
        # client is told to drop anything it holds that is no longer in the
        # changed set only when the count shrank. A shrinking count is the
        # only signal available, so report every current UID as changed and
        # let the client prune — this is what "full resync" means.
        if int(_count or 0) > len(records):
            return records, []
        return changed, []

    # ── vobject conversion ───────────────────────────────────────────────

    def to_vobject(self, record):
        """Serialise ``record`` to an iCalendar or vCard object.

        Returns the top-level object (``iCalendar`` for calendars, ``vCard``
        for addressbooks) or ``None`` when the record cannot be represented.
        """
        self.ensure_one()
        if self.dav_type == 'calendar':
            return self._to_icalendar(record)
        return self._to_vcard(record)

    def _to_icalendar(self, record):
        self.ensure_one()
        import vobject

        event = record

        calendar = vobject.iCalendar()
        vevent = calendar.add('vevent')
        vevent.add('uid').value = self.record_uid(event)

        if event.name:
            vevent.add('summary').value = event.name
        # Odoo stores naive UTC datetimes. Written as-is they become
        # "floating time" in iCalendar, which clients interpret in the local
        # zone — an event at 05:00 UTC then shows at 05:00 local. Attach UTC
        # so the serialiser writes the trailing Z.
        if event.start:
            vevent.add('dtstart').value = event.start.replace(tzinfo=tz.UTC)
        if event.stop:
            vevent.add('dtend').value = event.stop.replace(tzinfo=tz.UTC)
        # DTEND and DURATION are mutually exclusive in RFC 5545; vobject
        # refuses to serialise a VEVENT that carries both. DTEND wins when
        # we have it, DURATION is the fallback.
        if not event.stop and event.duration:
            vevent.add('duration').value = _duration_to_ical(event.duration)
        if event.location:
            vevent.add('location').value = event.location
        if event.description:
            vevent.add('description').value = event.description
        if event.allday:
            vevent.add('x-odoo-allday').value = 'TRUE'
        if event.privacy and event.privacy != 'public':
            vevent.add('class').value = (
                'PRIVATE' if event.privacy == 'private' else 'CONFIDENTIAL'
            )
        if event.show_as == 'free':
            vevent.add('transp').value = 'TRANSPARENT'
        else:
            vevent.add('transp').value = 'OPAQUE'
        if 'categ_ids' in event._fields:
            categories = event.categ_ids.mapped('name')
            if categories:
                vevent.add('categories').value = categories
        if 'videocall_location' in event._fields and event.videocall_location:
            vevent.add('url').value = event.videocall_location

        # Organiser and attendees. The organiser is the user_id partner;
        # without it clients cannot tell whose event this is.
        if event.user_id:
            organiser = vevent.add('organizer')
            organiser.value = 'mailto:%s' % (
                event.user_id.partner_id.email or event.user_id.email or '')
            organiser.params['CN'] = [_param_text(event.user_id.name)]
        for attendee in event.attendee_ids:
            mail = attendee.partner_id.email or attendee.email
            if not mail:
                continue
            line = vevent.add('attendee')
            line.value = 'mailto:%s' % mail
            line.params['CN'] = [_param_text(
                attendee.common_name or attendee.partner_id.name)]
            line.params['CUTYPE'] = ['INDIVIDUAL']
            line.params['ROLE'] = ['REQ-PARTICIPANT']
            line.params['PARTSTAT'] = [
                (attendee.state or 'needsAction').upper()
            ]
            line.params['RSVP'] = ['TRUE']

        # Recurrence. Odoo stores the rule on calendar.recurrence, not on
        # the event; expose it so clients do not see a single occurrence.
        # Occurrences are separate rows: they carry RECURRENCE-ID (their own
        # start) and the master's UID, which is how iCalendar says an
        # occurrence overrides a generated instance.
        recurrence = event.recurrence_id
        if recurrence and recurrence.rrule and not (
                'recurrence_id' in event._fields and event.recurrence_id):
            vevent.add('rrule').value = recurrence.rrule
        if 'recurrence_id' in event._fields and event.recurrence_id \
                and event.start:
            vevent.add('recurrence-id').value = event.start.replace(
                tzinfo=tz.UTC)
        if recurrence and recurrence.until:
            vevent.add('x-odoo-recurrence-until').value = (
                recurrence.until.strftime('%Y%m%dT%H%M%SZ')
            )

        rev = self.record_rev(event)
        if rev:
            vevent.add('rev').value = rev
        if 'dav_last_modified' in event._fields and event.dav_last_modified:
            vevent.add('last-modified').value = \
                event.dav_last_modified.replace(tzinfo=tz.UTC)
        if event.create_date:
            vevent.add('created').value = \
                event.create_date.replace(tzinfo=tz.UTC)
        return calendar

    def _to_vcard(self, record):
        self.ensure_one()
        import vobject

        card = vobject.vCard()
        card.add('uid').value = self.record_uid(record)
        card.add('fn').value = record.name or ''

        # N is mandatory in vCard 3.0. Odoo keeps a single name field, so
        # split it: last word is the family name, the rest is given names.
        # Strip quotes: imported contacts carry names like '"Sara Kempegard"',
        # and the quotes end up inside the N components ("Kempegard\"").
        name = (record.name or '').strip().strip('"\'').strip()
        if name:
            parts = name.split()
            family = parts[-1]
            given = ' '.join(parts[:-1])
            card.add('n').value = vobject.vcard.Name(
                family=family, given=given)

        if record.email:
            email = card.add('email')
            email.value = record.email
            email.params['TYPE'] = ['INTERNET', 'WORK']

        for field_name, tel_type in (('phone', 'WORK'), ('mobile', 'CELL')):
            value = record[field_name] if field_name in record._fields else None
            if value:
                tel = card.add('tel')
                tel.value = value
                tel.params['TYPE'] = [tel_type]

        # Address. res.partner and res.ppartner both use these names.
        address_fields = ('street', 'street2', 'city', 'zip',
                          'state_id', 'country_id')
        if any(record[f] for f in address_fields if f in record._fields):
            # Every ADR component must be a str. vobject's Address returns
            # False for components it considers empty, and its serialiser
            # then dies with "'bool' object is not iterable" — 135 of 4303
            # contacts failed on exactly this (ledningssystem 2026-10-25).
            adr = vobject.vcard.Address()
            adr.street = ' '.join(filter(None, [
                record.street if 'street' in record._fields else '',
                record.street2 if 'street2' in record._fields else '',
            ])) or ''
            adr.city = (record.city if 'city' in record._fields else '') or ''
            adr.region = (
                record.state_id.name
                if 'state_id' in record._fields and record.state_id else '') or ''
            adr.code = (record.zip if 'zip' in record._fields else '') or ''
            adr.country = (
                record.country_id.name
                if 'country_id' in record._fields and record.country_id else '') or ''
            card.add('adr').value = adr

        # ORG: the company a contact belongs to. res.ppartner keeps the
        # company as free text (company_name); res.partner as a parent.
        org = None
        if 'parent_id' in record._fields and record.parent_id:
            org = record.parent_id.name
        elif 'company_name' in record._fields and record.company_name:
            org = record.company_name
        elif 'is_company' in record._fields and record.is_company:
            org = record.name
        if org:
            card.add('org').value = [org]

        # CATEGORIES: res.partner uses category_id, res.ppartner
        # category_ids. Both are many2many to res.partner.category.
        for field_name in ('category_id', 'category_ids'):
            if field_name in record._fields and record[field_name]:
                card.add('categories').value = record[field_name].mapped('name')
                break

        if 'website' in record._fields and record.website:
            card.add('url').value = record.website
        if 'function' in record._fields and record.function:
            card.add('title').value = record.function
        if 'notes' in record._fields and record.notes:
            card.add('note').value = record.notes
        elif 'comment' in record._fields and record.comment:
            card.add('note').value = record.comment

        # PHOTO. res.partner.image_1920 is a base64 *string*; res.ppartner.image
        # is binary. vobject cannot serialise ENCODING=b (that is vCard 3.0
        # syntax it does not implement) — it fails with "unknown encoding: b"
        # — so the value goes in as plain base64 and vobject emits the
        # vCard 4.0 style line. Clients that only speak 3.0 simply ignore an
        # unparsable PHOTO; they do not reject the card.
        image = None
        for field_name in ('image_1920', 'image'):
            if field_name in record._fields and record[field_name]:
                image = record[field_name]
                break
        if image:
            if isinstance(image, bytes):
                image = image.decode('ascii', errors='ignore')
            image = str(image).strip().replace('\n', '').replace('\r', '')
            if image:
                card.add('photo').value = image

        rev = self.record_rev(record)
        if rev:
            card.add('rev').value = rev
        return card

    def from_vobject(self, vobject_item):
        """Convert an iCalendar/vCard object to Odoo field values.

        Accepts either a parsed vobject component or the raw ``str``/``bytes``
        body of a PUT request. Returns a dict of values, or ``None`` when the
        body is not the component this collection serves.
        """
        self.ensure_one()
        import vobject

        if isinstance(vobject_item, (str, bytes)):
            try:
                vobject_item = vobject.readOne(vobject_item)
            except Exception:
                return None
        if vobject_item is None:
            return None
        if self.dav_type == 'calendar':
            return self._from_icalendar(vobject_item)
        return self._from_vcard(vobject_item)

    def _from_icalendar(self, calendar):
        self.ensure_one()
        if getattr(calendar, 'name', '') != 'VCALENDAR':
            return None
        if not hasattr(calendar, 'vevent'):
            return None
        event = calendar.vevent
        values = {}
        # UID is what makes a PUT idempotent: without it every client save
        # creates a new row. Only set it when the collection has a UID field
        # and the client actually sent one.
        if self.field_uuid and hasattr(event, 'uid'):
            uid = str(event.uid.value or '').strip()
            if uid:
                values[self.field_uuid.name] = uid
        if hasattr(event, 'summary'):
            values['name'] = event.summary.value
        if hasattr(event, 'dtstart'):
            values['start'] = _ical_to_datetime(event.dtstart.value)
        if hasattr(event, 'dtend'):
            values['stop'] = _ical_to_datetime(event.dtend.value)
        if hasattr(event, 'duration') and 'duration' in self._model()._fields:
            values['duration'] = _ical_duration_to_hours(event.duration.value)
        if hasattr(event, 'location'):
            values['location'] = event.location.value
        if hasattr(event, 'description'):
            values['description'] = event.description.value
        if hasattr(event, 'class'):
            privacy = {'PRIVATE': 'private',
                       'CONFIDENTIAL': 'confidential'}.get(
                           str(event.class_.value).upper())
            if privacy:
                values['privacy'] = privacy
        if hasattr(event, 'transp'):
            values['show_as'] = (
                'free' if str(event.transp.value).upper() == 'TRANSPARENT'
                else 'busy')
        return values

    def _from_vcard(self, card):
        self.ensure_one()
        if getattr(card, 'name', '') != 'VCARD':
            return None
        model = self._model()
        values = {}

        if self.field_uuid and hasattr(card, 'uid'):
            uid = str(card.uid.value or '').strip()
            if uid:
                values[self.field_uuid.name] = uid

        if hasattr(card, 'fn'):
            values['name'] = card.fn.value
        elif hasattr(card, 'n'):
            name = card.n.value
            values['name'] = ' '.join(
                filter(None, [name.given, name.family]))

        if hasattr(card, 'email'):
            values['email'] = card.email.value

        for child in card.getChildren():
            child_name = child.name.lower()
            params = {
                key.upper(): value
                for key, value in (child.params or {}).items()
            }
            types = [str(t).upper() for t in params.get('TYPE', [])]
            if child_name == 'tel':
                if 'CELL' in types and 'mobile' in model._fields:
                    values['mobile'] = child.value
                elif 'phone' in model._fields:
                    values['phone'] = child.value
            elif child_name == 'adr':
                values.update(self._vcard_address(child.value, model))
            elif child_name == 'org':
                org = child.value
                if isinstance(org, (list, tuple)):
                    org = org[0] if org else ''
                org = str(org or '').strip()
                if org:
                    if 'company_name' in model._fields:
                        values['company_name'] = org
                    elif 'parent_id' in model._fields:
                        values['parent_id'] = self._resolve_company(org).id
            elif child_name == 'categories':
                categories = child.value
                if isinstance(categories, (list, tuple)):
                    names = [str(c).strip() for c in categories if c]
                else:
                    names = [c.strip() for c in str(categories).split(',')
                             if c.strip()]
                if names:
                    tag_ids = [
                        self._resolve_category(name).id for name in names
                    ]
                    for field_name in ('category_id', 'category_ids'):
                        if field_name in model._fields:
                            values[field_name] = [(6, 0, tag_ids)]
                            break
            elif child_name == 'url' and 'website' in model._fields:
                values['website'] = child.value
            elif child_name == 'title' and 'function' in model._fields:
                values['function'] = child.value
            elif child_name == 'note':
                if 'notes' in model._fields:
                    values['notes'] = child.value
                elif 'comment' in model._fields:
                    values['comment'] = child.value
        return values

    def _vcard_address(self, adr, model):
        """Map a vCard ADR value onto the model's address fields."""
        values = {}
        if isinstance(adr, (list, tuple)):
            parts = [str(p or '') for p in adr]
        else:
            parts = str(adr or '').split(';')
        parts = [p.strip() for p in parts]
        while len(parts) < 7:
            parts.append('')
        # ADR: PO box; extended; street; locality; region; postal code;
        # country
        if parts[2] and 'street' in model._fields:
            values['street'] = parts[2]
        if parts[1] and 'street2' in model._fields:
            values['street2'] = parts[1]
        if parts[3] and 'city' in model._fields:
            values['city'] = parts[3]
        if parts[5] and 'zip' in model._fields:
            values['zip'] = parts[5]
        if parts[4] and 'state_id' in model._fields:
            state = self.env['res.country.state'].search([
                '|', ('name', '=', parts[4]), ('code', '=', parts[4]),
            ], limit=1)
            if state:
                values['state_id'] = state.id
        if parts[6] and 'country_id' in model._fields:
            country = self.env['res.country'].search([
                '|', ('name', '=', parts[6]), ('code', '=', parts[6]),
            ], limit=1)
            if country:
                values['country_id'] = country.id
        return values

    def _resolve_company(self, name):
        company = self.env['res.partner'].sudo().search([
            ('is_company', '=', True), ('name', '=', name),
        ], limit=1)
        if not company:
            company = self.env['res.partner'].sudo().create({
                'name': name,
                'is_company': True,
            })
        return company

    def _resolve_category(self, name):
        category = self.env['res.partner.category'].sudo().search(
            [('name', '=', name)], limit=1)
        if not category:
            category = self.env['res.partner.category'].sudo().create({
                'name': name,
            })
        return category


def _param_text(value):
    """Make a value safe for an iCalendar *parameter*.

    A parameter value may not contain a bare double quote: vobject raises
    "Double quotes aren't allowed in parameter values". Names like
    'Ann-Catrin "AC" Polstam' are common in real address books, so the
    quotes are dropped rather than escaped — RFC 6868's ^' escaping is not
    understood by every client, and losing a nickname's quotes is harmless.
    """
    if not value:
        return ''
    return str(value).replace('"', '').replace('\r', ' ').replace('\n', ' ')


def _duration_to_ical(hours):
    """Odoo stores duration as float hours; iCalendar DURATION is ISO 8601."""
    total_minutes = int(round((hours or 0) * 60))
    sign = '-' if total_minutes < 0 else ''
    total_minutes = abs(total_minutes)
    return '%sPT%dH%dM' % (
        sign, total_minutes // 60, total_minutes % 60)


def _ical_to_datetime(value):
    """Normalise an iCalendar date/datetime to an Odoo naive UTC datetime."""
    import datetime
    import pytz

    if isinstance(value, datetime.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(pytz.UTC).replace(tzinfo=None)
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    return None


def _ical_duration_to_hours(value):
    """Parse an iCalendar DURATION (e.g. PT1H30M) into float hours."""
    import re

    match = re.match(
        r'^(?P<sign>[+-])?P(?:(\d+)W)?(?:(\d+)D)?'
        r'(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$',
        str(value or '').strip(),
    )
    if not match:
        return 0.0
    weeks, days, hours, minutes, seconds = (
        int(match.group(i) or 0) for i in range(2, 7)
    )
    total = (weeks * 7 * 24) + (days * 24) + hours
    total += minutes / 60.0 + seconds / 3600.0
    if match.group('sign') == '-':
        total = -total
    return round(total, 2)
