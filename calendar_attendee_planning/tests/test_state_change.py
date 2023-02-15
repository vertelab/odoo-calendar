from odoo import fields
from odoo.tests import common
import datetime
import logging

_logger = logging.getLogger(__name__)

#test color change, state change when write to attendee, check overlapping, check if person has hr.leave 

class TestAttendeeInteractions(common.SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start = datetime.datetime(2023, 2, 2, 10) 
        cls.stop = datetime.datetime(2023, 2, 2, 11)
        cls.start2 = datetime.datetime(2023, 2, 2, 10, 15)
        cls.stop2 = datetime.datetime(2023, 2, 2, 11, 15) 
        cls.created_event_earlier = cls.env['calendar.event'].create({'name': 'test', 'start': str(cls.start), 'stop': str(cls.stop), 'partner_ids': [[6, False, [3]]],})
        cls.created_event_later = cls.env['calendar.event'].create({'name': 'test', 'start': str(cls.start2), 'stop': str(cls.stop), 'partner_ids': [[6, False, [3]]],})

    def test_color_change(self):
        self.created_event_later.attendee_ids[0].write({'event_date_start': self.start2, 'event_date_end': self.stop2})
        self.assertEqual(self.created_event_later.attendee_ids[0].color, 1)
