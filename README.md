

## Porteringsstatus

18.0 är baseline. 19.0/20.0 visar om p-filen har ett villkor för utgåvan
— inte om grenen finns. Blockerare är `depends` som saknas i 20.0
(kärna + alla 20.0-grenar).

| Modul | Beskrivning | Manifest | p-fil | 19.0 | 20.0 | Blockerare |
|---|---|---|---|---|---|---|
| calander_full_form | To be able to open calendar form view instead of a popup. | 1.0.0 | 0 | — | — | — |
| calendar_ai | OKF-indexering av kalenderhändelser (calendar.event) | 1.0.0 | 1 | — | — | — |
| calendar_attendee_planning | Adds attendee views to the calendar. | 1.0.1 | 0 | — | — | `web_timeline` |
| calendar_caldav | CalDAV support for Odoo Calendar | 1.0.0 | 1 | — | ✓ | — |
| calendar_dav | Extension of the base_dav module to work better with the ... | 1.0.0 | 0 | — | — | — |
| calendar_ics | Subscription on calendar.ics-urls. | 1.0.0 | 0 | — | — | — |
| calendar_ics_invitations | Outlook/Teams compatible iTIP meeting invitations and can... | 1.0.0 | 0 | — | — | — |
| calendar_onboarding | Onboardingskurs: kalender, kontakter och DAV-synk | 1.0.0 | 0 | — | — | — |
| calendar_public_holiday_nager | Get Public Holidays from Nager.Date . | 1.0.0 | 0 | — | — | `calendar_public_holiday` |
| calendar_resource_booking | Adds material resource to book at an appointment. | 1.0.1 | 0 | — | — | — |
| calendar_skills_allergies_glue | Compare contract and partner skills & allergies. | 1.0.0 | 0 | — | — | `contract_attendee` `contract_allergic` `contract_cleaner` `contract` |
| calendar_sync | Syncs the Odoo calendar with other apps. | 1.0.0 | 0 | — | — | — |
| extended_calendar_notifications | Module extends functionality for calandar events. | 1.1.0 | 0 | — | — | — |
| ics_import_holidays | Import holidays will update monthly basis so you are alwa... | 1.0.0 | 0 | — | — | — |
| one_page_website_calendar | Schedule bookings with clients. | 1.0.0 | 0 | — | — | — |
| website_booking_checkout | Product Booking Checkout. | 1.0.0 | 1 | — | ✓ | — |
| website_calendar_ce | Schedule bookings with clients. | 1.0.0 | 2 | — | ✓ | — |
| website_calendar_event | Schedule bookings with clients. | 1.0.0 | 0 | — | — | — |
| website_calendar_product_resource | Calendar Product Resource. | 1.0.0 | 0 | — | — | — |
| website_calendar_slot_range | Booking a range of time slot. | 1.0.0 | 0 | — | — | — |
| website_calendar_waitlist | Schedule bookings with clients. | 1.0.0 | 1 | — | ✓ | — |
| website_form_calendar | Add a task suggestion form to your website. | 1.0.0 | 0 | — | — | `website_form` |
| website_sale_rental_booking | Webiste Sale Rental Booking. | 1.0.0 | 0 | — | — | `sttl_sale_rental` |
