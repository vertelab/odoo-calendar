# -*- coding: utf-8 -*-
# Copyright 2026 Vertel Sverige AB (<https://vertel.se>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""VTODO serialisation (RFC 5545 §3.6.2, CalDAV RFC 4791 §4).

Thunderbird keeps its tasks in a CalDAV collection that advertises
``VTODO`` in ``supported-calendar-component-set``. Without that line the
client hides the calendar from its task view entirely, which is why tasks
"did not work" while the calendar did.

A VTODO is stored as a ``project.task`` with no project — that is exactly
what Odoo's own Att-göra view (``project_todo``) is: ``project_id`` is
False and the task is filtered by ``user_ids``. The mapping is therefore
one-to-one and a task created in Thunderbird shows up in
``/odoo/to-do`` without any glue.

STATUS is the only field that does not map straight across. Odoo's task
``state`` has six values and iCalendar has four, so the mapping is
deliberately lossy in one direction: several Odoo states read as
``IN-PROCESS``. Writing back is unambiguous.
"""

import logging
from datetime import date, datetime, time

import pytz
from icalendar import Calendar, Todo

_logger = logging.getLogger(__name__)

#: iCalendar STATUS → ``project.task.state``.
STATUS_TO_STATE = {
    'NEEDS-ACTION': '01_in_progress',
    'IN-PROCESS': '01_in_progress',
    'COMPLETED': '1_done',
    'CANCELLED': '1_canceled',
}

#: ``project.task.state`` → iCalendar STATUS. Several Odoo states collapse
#: into IN-PROCESS because iCalendar has no equivalent for them.
STATE_TO_STATUS = {
    '01_in_progress': 'IN-PROCESS',
    '02_changes_requested': 'IN-PROCESS',
    '03_approved': 'IN-PROCESS',
    '04_waiting_normal': 'IN-PROCESS',
    '1_done': 'COMPLETED',
    '1_canceled': 'CANCELLED',
}

#: ``project.task.priority`` is a two-value selection; iCalendar PRIORITY
#: runs 0-9 where 1 is highest. 0 means "undefined", so anything from 1 to
#: 4 is treated as high and the rest as low.
HIGH_PRIORITY_MAX = 4


def _as_utc(value):
    """Naive UTC datetime, the form Odoo stores."""
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(pytz.UTC).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return None


def _priority_to_odoo(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return '0'
    if number == 0:
        return '0'
    return '1' if number <= HIGH_PRIORITY_MAX else '0'


def _priority_to_ical(task):
    return 1 if task.priority == '1' else 0


def _description_to_text(value):
    """Odoo stores description as HTML; a VTODO wants plain text."""
    if not value:
        return ''
    if '<' not in value:
        return value
    try:
        from odoo.tools import html2plaintext
        return html2plaintext(value)
    except Exception:  # noqa: BLE001 - never fail a sync over formatting
        return value


def build_vtodo(task, base_url=None):
    """One ``VTODO`` component for ``task``."""
    todo = Todo()
    todo.add('uid', task.caldav_uuid or 'task-%s@odoo' % task.id)
    todo.add('summary', task.name or '')
    todo.add('dtstamp', datetime.utcnow())
    todo.add('last-modified', task.write_date or datetime.utcnow())
    todo.add('created', task.create_date or datetime.utcnow())

    description = _description_to_text(task.description)
    if description:
        todo.add('description', description)

    if task.date_deadline:
        todo.add('due', task.date_deadline)

    status = STATE_TO_STATUS.get(task.state)
    if status:
        todo.add('status', status)

    if task.state == '1_done':
        todo.add('percent-complete', 100)
        # iCalendar wants the completion moment; Odoo has no field for it,
        # so the last write is the closest honest answer.
        todo.add('completed', task.write_date or datetime.utcnow())
    elif 'progress' in task._fields and task.progress:
        todo.add('percent-complete', int(task.progress))
    else:
        todo.add('percent-complete', 0)

    priority = _priority_to_ical(task)
    if priority:
        todo.add('priority', priority)

    if task.tag_ids:
        todo.add('categories', [tag.name for tag in task.tag_ids])

    if task.parent_id and task.parent_id.caldav_uuid:
        todo.add('related-to', task.parent_id.caldav_uuid)

    if base_url:
        todo.add('url', '%s/odoo/to-do/%s' % (base_url.rstrip('/'), task.id))

    return todo


def odoo_task_to_icalendar(task, base_url=None):
    cal = Calendar()
    cal.add('prodid', '-//Odoo Calendar//EN')
    cal.add('version', '2.0')
    cal.add_component(build_vtodo(task, base_url))
    return cal


def parse_vtodo(ical_str):
    """The values a ``project.task`` needs, from a VTODO payload.

    Returns ``None`` when the payload holds no VTODO at all — a client may
    PUT a VEVENT into a task collection by mistake, and that must be a
    clear error rather than an empty task.
    """
    cal = Calendar.from_ical(ical_str)
    components = cal.walk('VTODO')
    if not components:
        return None
    todo = components[0]

    values = {
        'name': str(todo.get('summary') or ''),
        'description': str(todo.get('description') or ''),
    }

    due = todo.get('due')
    if due is not None:
        values['date_deadline'] = _as_utc(due.dt)

    status = todo.get('status')
    if status:
        state = STATUS_TO_STATE.get(str(status).upper())
        if state:
            values['state'] = state

    # ``progress`` comes from project_todo, which is not a hard dependency
    # of this module; write it only when the field is actually there.
    percent = todo.get('percent-complete')
    if percent is not None:
        try:
            values['_progress'] = float(percent)
        except (TypeError, ValueError):
            pass
    elif values.get('state') == '1_done':
        values['_progress'] = 100.0

    priority = todo.get('priority')
    if priority is not None:
        values['priority'] = _priority_to_odoo(priority)

    categories = todo.get('categories')
    if categories is not None:
        # icalendar returns a vCategory that may hold several entries.
        names = getattr(categories, 'cats', None) or [categories]
        values['_categories'] = [str(name) for name in names]

    uid = todo.get('uid')
    if uid:
        values['caldav_uuid'] = str(uid)

    return values
