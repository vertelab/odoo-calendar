from odoo.tests import common
from ..services.caldav import odoo_event_to_icalendar, icalendar_to_odoo_event, generate_sync_report
from datetime import datetime
import pytz

class TestCalDAV(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.event = self.env["calendar.event"].create({
            "name": "Test Event",
            "start_datetime": datetime(2023, 1, 1, 12, 0, tzinfo=pytz.UTC),
            "stop_datetime": datetime(2023, 1, 1, 13, 0, tzinfo=pytz.UTC),
            "description": "Test Description",
        })

    def test_odoo_event_to_icalendar(self):
        """Testar konvertering från Odoo-event till iCalendar."""
        ical = odoo_event_to_icalendar(self.event)
        self.assertIn("VEVENT", str(ical))
        self.assertIn("Test Event", str(ical))
        self.assertIn("Test Description", str(ical))

    def test_icalendar_to_odoo_event(self):
        """Testar konvertering från iCalendar till Odoo-event."""
        ical_str = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Odoo Calendar//SE
BEGIN:VEVENT
UID:test-uid
SUMMARY:Updated Event
DTSTART:20230101T120000Z
DTEND:20230101T130000Z
DESCRIPTION:Updated Description
END:VEVENT
END:VCALENDAR"""
        event = icalendar_to_odoo_event(ical_str, self.event)
        self.assertEqual(event.name, "Updated Event")
        self.assertEqual(event.description, "Updated Description")

    def test_controller_routes(self):
        """Testar att controllerns routes är korrekt registrerade."""
        from odoo.addons.calendar_caldav.controllers.main import CalDAVController
        controller = CalDAVController()
        # Verifiera att metoder finns
        self.assertTrue(hasattr(controller, "get_event"))
        self.assertTrue(hasattr(controller, "update_event"))
        self.assertTrue(hasattr(controller, "propfind"))
        self.assertTrue(hasattr(controller, "report"))

    def test_report_method(self):
        """Testar att REPORT-generering fungerar."""
        events = self.env["calendar.event"].search([])
        report = generate_sync_report(events)
        self.assertIn("<d:multistatus", report)
        self.assertIn("/caldav/events/", report)

    def test_rrule_conversion(self):
        """Testar konvertering av återkommande händelser."""
        self.event.write({"recurrency": "WEEKLY"})
        ical = odoo_event_to_icalendar(self.event)
        self.assertIn("RRULE:FREQ=WEEKLY", str(ical))
        
        # Testa återskapande från iCalendar
        ical_str = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Odoo Calendar//SE
BEGIN:VEVENT
UID:test-uid
SUMMARY:Recurring Event
DTSTART:20230101T120000Z
DTEND:20230101T130000Z
RRULE:FREQ=WEEKLY
END:VEVENT
END:VCALENDAR"""
        event = icalendar_to_odoo_event(ical_str, self.event)
        self.assertEqual(event.recurrency, "WEEKLY")