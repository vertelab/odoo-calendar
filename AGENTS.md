We program in English. All code, comments, docstrings, and commit messages must be written in English.

## Modules

| Module | Purpose |
| --- | --- |
| `calendar_ics_invitations` | Outlook/Exchange/Teams compatible iTIP invitations, updates and cancellations. Overrides `calendar.event._get_ics_file()` (stable `UID`, `SEQUENCE`, `METHOD`, `ORGANIZER`/`ATTENDEE` with `PARTSTAT`), and — together with `extended_calendar_notifications` — distributes attendee responses. |
| `extended_calendar_notifications` | Cancellation and (since 18.0.1.1.0) attendee-response notifications. Attaches the `METHOD:CANCEL` / `METHOD:REQUEST` ICS payloads built by `calendar_ics_invitations`. |
| `calendar_ics` | ICS subscriptions (legacy `icalendar`-based generator, unrelated to invitations). |
| `calendar_caldav` | CalDAV server (see below). |
| `calendar_ai` | OKF indexing of `calendar.event` (see below). One concept per stakeholder: a `company` concept owned by the event's company, plus a `personal` concept per attendee who is a user. |

### Upgrade check — ICS invitations

`calendar_ics_invitations` overrides three core surfaces. Re-verify them when
upgrading Odoo, because a core change makes the override silently stop working:

* `calendar.event._get_ics_file()` — the override surface (core signature is
  `_get_ics_file(self)`; our optional `method` argument is an extension).
* `calendar.attendee._send_mail_to_attendees()` — attaches the payload as
  `invitation.ics`.
* `calendar.attendee.write()` — the hook the response distribution relies on.

Both `calendar_ics_invitations` and `extended_calendar_notifications` must be
version-bumped and redeployed together; the cancellation and response paths
live in the latter.

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

## Current State — Calendar AI (`calendar_ai`)

OKF indexing of `calendar.event`. The bridge owns the event's **sources**;
`ai.okf.mixin` (in `ai_agent_core`) owns the fields and the dirty flag.

### One event, one concept per stakeholder

An event is personal to the person invited ("what do I have booked in
October") *and* organisational knowledge for the company. The same event
therefore yields:

```
   calendar.event,42                          company   (the event's company)
   calendar.event,42,user.7                   personal  (attendee A)
   calendar.event,42,user.9                   personal  (attendee B)
```

Owners are expressed through `_okf_owner_vals_list()`. `_okf_index_record()`
writes one concept per owner and sets the owner segment in `concept_key`
automatically — the bridge does not touch `_okf_concept_key`. The owner
segment is only added when a post has **more than one** owner, so a
single-owner post keeps the plain `<model>,<id>` key.

Attendees are `partner_ids` that map to a `res.users`. External contacts
(no user) get no personal concept — the event still gets its `company`
concept.

### Company resolution — `company_id` does not exist in core

`calendar.event` has **no `company_id` in Odoo 18 core**; the calendar is not
multi-company in CE. The field comes from OCA's
`calendar_event_multi_company`, which is **not installed** here.
`_okf_company_id()` therefore resolves in three steps:

1. `company_id` if the field exists and is set (OCA module installed — then
   it is authoritative),
2. the organiser's company (`user_id.company_id`),
3. `env.company` as a last resort (the organiser is not a required field).

**Lesson (2026-10-07):** the original `_okf_owner_vals()` read `self.company_id`
directly and raised `AttributeError` the moment the module ran. It went
unnoticed because `calendar_ai` had never been installed or tested. Installing
and testing the module is what surfaced it.

### Attendee list is capped in personal concepts

`_okf_summary_source(owner_vals=None)` omits the attendee list when the owner
is a **user**: another attendee's name should not land in someone's personal
memory, and an external attendee's name should not land there at all. The
`company` concept keeps the list — it is shared between those entitled to it.

Called without `owner_vals` (an older core), the list is kept. That is the
harmless case; no crash.

### Volume cap per event

`_okf_owner_limit()` (system parameter `calendar_ai.okf_owner_limit`, default
25) caps how many owners — and therefore concepts — one event may produce.
`_okf_dirty_fields()` contains `partner_ids`, so an attendee change rewrites
**every** owner's concept; the cap bounds that cost. The company is always
included, so the cap counts attendees only. A capped event is logged.

### Measured cost — embedding dominates (2026-10-07)

Measured on a warm database, 5 attendees per event:

```
   per event:      2.47 s      (6 concepts)
   per concept:    0.41 s
   embedding call: 0.27 s      (Bifrost HTTP, one per concept)
   _okf_upsert without embedding: 0.115 s
```

The embedding call is ~70 % of the cost, and it is **one HTTP request per
concept**. Since one event now yields N+1 concepts instead of 1, indexing
costs N+1 times as many embedding calls. Projected over ~21 000 events with
5 attendees: ~126 000 embedding calls, ~14 hours of work.

The OKF cron has a 4-minute time budget per 5-minute round, so it drains
~100 events per round — a full pass takes hours of wall-clock time, which is
acceptable. The **resource cost** (6× the embedding calls) is the real
issue and is tracked as a separate change: batched embedding in
`ai_agent_core`. It is out of scope here.

### Upgrade check — calendar_ai

* `_okf_owner_vals_list()`, `_okf_concept_key(owner_id=...)`,
  `_okf_owner_vals_list`-aware `_okf_upsert`/`DISTINCT ON`/`_latest_per_key`
  — all in `ai_agent_core` ≥ 18.0.1.302. `tests/test_calendar_okf_contract.py`
  fails if the contract is missing.
* `_okf_summary_source(owner_vals=...)` — the optional argument added in
  `ai_agent_core` 18.0.1.303. Without it the attendee list is never capped.
* `calendar.event` gains `company_id` only with OCA's
  `calendar_event_multi_company`; `_okf_company_id()` handles both cases.
