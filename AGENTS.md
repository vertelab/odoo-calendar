We program in English. All code, comments, docstrings, and commit messages must be written in English.

## Module icons and banners
When creating or updating module icons and banners:
- Place in `static/description/`
- Icon: 140x140 pixels, saved as `icon_140x140.svg` and `icon.png`
- Banner: 560x280 pixels, saved as `banner_560x280.svg` and `banner.png`
- Use the existing color scheme as reference (e.g., from `calendar_ics`).
- Generate PNG from SVG using cairosvg:
  ```python
  cairosvg.svg2png(url='icon_140x140.svg', write_to='icon.png', output_width=140, output_height=140)
  cairosvg.svg2png(url='banner_560x280.svg', write_to='banner.png', output_width=560, output_height=280)
  ```

## Current State — CalDAV Module (`calendar_caldav`)

### Architecture
- **Flat CalDAV hierarchy**: `/caldav/` IS the calendar AND the principal AND the calendar-home-set (all point to itself).
- **Events**: `/caldav/events/<event_id>.ics` AND `/caldav/<uuid>.ics` (Thunderbird uses `/caldav/<uuid>.ics` for PUT).
- **Auth**: `auth="public"` + manual `_basic_auth()` that iterates `db.exp_list()` for multi-database support. Returns proper 401 with `WWW-Authenticate: Basic`.
- **PUT on `/caldav/`**: Thunderbird sends ALL events (multi-VEVENT) in one PUT body. Our handler loops over every VEVENT, wrapping each in its own Calendar before calling `icalendar_to_odoo_event()` to avoid parsing the first VEVENT repeatedly.
- **Timezone handling**: Thunderbird sends `Europe/Stockholm`-aware datetimes. Convert `astimezone(pytz.UTC).replace(tzinfo=None)` before passing to Odoo.
- **`icalendar_to_odoo_event`**: must use `request.env` (not `event.env`) since `event` is `None` for new-event creation. `event.env` crashes when event is a fresh `browse()` recordset or `None`.

### Key Files
- `controllers/main.py`: All CalDAV logic (PROPFIND, GET, PUT, REPORT, OPTIONS, HEAD dispatch).
- `services/caldav.py`: iCalendar ↔ Odoo event conversion.
- `models/calendar_event.py`: `uuid`, `dav_last_modified` fields.
- `hooks.py`: `post_init_hook` to fill NULL UUIDs.
- `models/ir_http.py`: Odoo `_auth_method_user` override (secondary — CalDAV uses manual auth now).

### Thunderbird Flow (verified working)
1. GET `/caldav/` → 401 → retry with auth → 200 (ICS with all events) ← **critical**
2. PROPFIND `/caldav/` (Depth 0) → 200 (resourcetype: collection + calendar, owner, current-user-principal, calendar-home-set, calendar-color, current-user-privilege-set)
3. PROPFIND `/caldav/` (Depth 1) → 200 (calendar + events)
4. (Optional) REPORT calendar-multiget → 200 (event data in iCalendar format)
5. GET `/caldav/events/<id>.ics` → 200 (individual event iCal)
6. PUT `/caldav/events/<id>.ics` → event update
7. PUT `/caldav/` → multi-VEVENT body, updates existing + creates new events

### Why It Works Now
- **GET `/caldav/` returns ICS with all events** (Thunderbird requires this to confirm the URL is a calendar — HTML breaks it)
- **Flat hierarchy** — no principal/calendars intermediate layers to confuse clients
- **All PROPFIND properties in 200 response**: `resourcetype`, `displayname`, `calendar-description`, `calendar-color`, `getcontenttype`, `owner`, `current-user-principal`, `calendar-home-set`, `current-user-privilege-set`
- **OPTIONS without auth** per RFC 4918 so Thunderbird sees DAV capabilities immediately
- **ETags quoted** per HTTP spec

### Known Issues
- All events share same `write_date` (demo data) → same ETag. Functional but not ideal.
- UUIDs in DB are corrupted (same UUID `eb1a5004-...` for all events). Workaround: using event IDs directly.
- PROPFIND `/` (root URL) returns 400 (CSRF) — Thunderbird probes it but doesn't fail.

### Bugs Fixed
- **2026-06-04**: PUT on `/caldav/` from Thunderbird sent multi-VEVENT body but only first VEVENT was processed. Fixed: loop all VEVENTs, wrap each in its own Calendar before calling `icalendar_to_odoo_event()`.
- **2026-06-04**: New event creation crashed with `'NoneType' object has no attribute 'env'`. Fixed: use `request.env` instead of `event.env` in `icalendar_to_odoo_event`.
- **2026-06-04**: New event creation failed with "Datetime field expects a naive datetime". Fixed: convert timezone-aware datetimes to naive UTC via `astimezone(pytz.UTC).replace(tzinfo=None)`.
- **2026-06-04**: Thunderbird PUT to `/caldav/<uuid>.ics` returned 404. Fixed: added `/caldav/<string:event_uuid>.ics` route alongside existing `/caldav/events/<string:event_uuid>.ics`.
