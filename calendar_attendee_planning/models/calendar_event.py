# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class CalendarEventModify(models.Model):
    _inherit = "calendar.event"

    @api.model
    def create(self, vals_list):
        res = super().create(vals_list)

        my_overlap = self.check_overlapping()
        for overlap in my_overlap:
            for attendee in overlap.attendee_ids:
                attendee.set_state()
        return res

    def write(self, vals):
        res = None
        for event in self:
            if 'active' in vals.keys() and vals['active'] == False:
                vals['attendee_ids'] = [(5, 0, 0)]

            pre_move_overlap = event.check_overlapping()

            res = super().write(vals)
            if res == False:
                break

            post_move_overlap = event.check_overlapping()
            for attendee in event.attendee_ids:
                #if len(new) != 0:
                attendee.set_state()

            for attendee in pre_move_overlap.attendee_ids:
                attendee.set_state()

            for attendee in post_move_overlap.attendee_ids:
                attendee.set_state()
        
        return res
    
    def unlink(self):
        pre_move_overlap = self.check_overlapping()

        super().unlink()

        for overlap in pre_move_overlap:
            for attendee in overlap.attendee_ids:
                attendee.set_state()

        return True

    def check_overlapping(self):
        overlapping_events = self.env['calendar.event']
        for event in self:
            overlapping_events |= self.search([
                    '&',
                        '|',
                            '&',
                                ('start','<',event.start),
                                ('stop','>',event.start),
                            '|',
                                '&',
                                    ('start','<',event.stop),
                                    ('stop','>',event.stop),
                                '|',
                                    '&',
                                        ('start','<=',event.start),
                                        ('stop','>=',event.stop),
                                    '&',
                                        ('start','>=',event.start),
                                        ('stop','<=',event.stop),
                        # '&',
                        # #('partner_id', 'in', attendee_partners),
                        #     ('partner_id', '=', event.partner_id.id),
                        ('id', '!=', event.id),
                    ])
            
        return overlapping_events
