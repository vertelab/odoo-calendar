=======================
Calendar ICS Invitations
=======================

Outlook / Exchange / Microsoft Teams compatible iTIP meeting invitations,
updates and cancellations for Odoo 18.

Description
===========

Odoo core builds meeting invitations from an iTIP payload that Outlook and
Teams do not recognise as a real invitation: no ``METHOD``, a ``UID``
containing spaces, bare ``ATTENDEE`` lines and no ``SEQUENCE``. Recipients get
a static ``METHOD:PUBLISH`` entry with no Accept / Decline / Tentative buttons,
and a reschedule arrives as a new, unrelated entry.

This module overrides ``calendar.event._get_ics_file()`` so the generated
``VEVENT`` is compliant and Outlook/Exchange/Teams aware:

* ``METHOD:REQUEST`` for invitations and updates, ``METHOD:CANCEL`` for
  cancellations.
* A stable, space-free ``UID`` persisted on the event, so a reschedule updates
  the original entry instead of duplicating it.
* A persisted ``SEQUENCE``, incremented on scheduling-relevant changes.
* ``ORGANIZER`` and ``ATTENDEE`` lines carrying ``CN``,
  ``ROLE=REQ-PARTICIPANT``, ``PARTSTAT`` and ``RSVP=TRUE``, with a lowercase
  ``mailto:`` scheme.
* Exchange-compatible ``STATUS``, ``TRANSP``, ``CLASS``, ``DTSTAMP`` and
  ``LAST-MODIFIED``.

Attendee responses (accepted / declined / tentative) are distributed to the
other attendees as iTIP updates, so participants in Outlook and Teams see each
other's response without opening Odoo. This part is implemented together with
``extended_calendar_notifications``.

The existing invitation, reschedule and cancellation mail templates, recipient
selection and attachment naming are left untouched — only the ICS payload
changes, plus one dedicated response notification.

Dependencies
============

``calendar``, ``mail``, ``extended_calendar_notifications``.

Payload contract
================

Every outgoing ``text/calendar`` part is built by
``calendar.event._get_ics_file(method='REQUEST')`` (core's signature is
``_get_ics_file(self)``; the ``method`` argument is our optional extension, so
core's call site keeps working). The payload is produced by core and re-parsed
with ``vobject`` so the Outlook/Exchange/Teams properties can be set without
copying core's generator.

====================  ==========================================================
Property              Value
====================  ==========================================================
``VCALENDAR.METHOD``  ``REQUEST`` for invitations/updates, ``CANCEL`` for cancellations
``VCALENDAR.PRODID``  ``-//Vertel//Odoo Calendar//EN``
``VEVENT.UID``         persisted ``ics_uid`` — ``<id>-<uuid4>@<dbname>``, no whitespace
``VEVENT.SEQUENCE``   persisted ``ics_sequence``, incremented on scheduling-relevant writes
``VEVENT.STATUS``     ``CONFIRMED``, or ``CANCELLED`` for a cancellation
``VEVENT.TRANSP``     ``OPAQUE``, or ``TRANSPARENT`` when the event is marked free
``VEVENT.CLASS``      ``PUBLIC``, or ``PRIVATE`` when ``privacy`` is ``private`` or ``confidential``
``DTSTAMP``           now, UTC
``LAST-MODIFIED``     ``write_date``, UTC
``ORGANIZER``         ``mailto:<lowercase email>`` + ``CN``
``ATTENDEE``          ``mailto:`` + ``ROLE=REQ-PARTICIPANT``, ``PARTSTAT``, ``RSVP=TRUE``, ``CN``
====================  ==========================================================

``PARTSTAT`` mapping from ``calendar.attendee.state``: ``needsAction`` →
``NEEDS-ACTION``, ``tentative`` → ``TENTATIVE``, ``declined`` → ``DECLINED``,
``accepted`` → ``ACCEPTED``; anything unknown falls back to ``NEEDS-ACTION``.
Attendees without an email are skipped.

Cancellation path
=================

``extended_calendar_notifications.unlink()`` bumps ``ics_sequence`` and attaches
a ``METHOD:CANCEL`` payload to the existing ``calendar_event_cancelled`` mail.
The mail template's subject and body are unchanged.

Response distribution
=====================

``calendar.attendee.write()`` detects a ``state`` transition to ``accepted``,
``declined`` or ``tentative`` and sends the other attendees (excluding the
responder and the organizer) an iTIP update carrying the new ``PARTSTAT`` and
an incremented ``SEQUENCE``, using the dedicated
``calendar_template_meeting_response`` template. The organizer keeps the core
chatter message. A ``skip_response_update`` context flag prevents the
flow from re-triggering itself.

Core coupling points (re-check on Odoo upgrade)
===============================================

* ``calendar.event._get_ics_file()`` — the override surface. If core changes
  its signature, the override silently stops being called.
* ``calendar.attendee._send_mail_to_attendees()`` — the consumer that attaches
  the payload as ``invitation.ics``.
* ``calendar.attendee.write()`` — the hook the response distribution relies on.

Credits
=======

Authors
~~~~~~~
* Vertel AB

Maintainers
~~~~~~~~~~~
This module is maintained by Vertel AB.

You can find this module at: https://vertel.se/apps/odoo-calendar/calendar_ics_invitations.
This module is maintained at: https://github.com/vertelab/odoo-calendar.
