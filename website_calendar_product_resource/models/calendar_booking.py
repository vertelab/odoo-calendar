import json
import calendar as cal
import random
import pytz
from dateutil.rrule import rrule, DAILY
import pandas
from datetime import datetime, timedelta, time
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from babel.dates import format_datetime

from odoo import api, fields, models, _
from odoo.tools.misc import get_lang
from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.http_routing.models.ir_http import slug
from odoo.exceptions import ValidationError


class CalendarBooking(models.Model):
    _inherit = "calendar.booking.type"

    product_ids = fields.Many2many("product.product", "calendar_booking_type_product_rel", string="Products")

    def _get_product_booking_slots(self, timezone, product=None):
        """ Fetch available slots to book an booking
            :param timezone: timezone string e.g.: 'Europe/Brussels' or 'Etc/GMT+1'
            :param employee: if set will only check available slots for this employee
            :returns: list of dicts (1 per month) containing available slots per day per week.
                      complex structure used to simplify rendering of template

            TODO: this needs to be improved if it will be used
        """
        self.ensure_one()
        appt_tz = pytz.timezone(self.booking_tz)
        requested_tz = pytz.timezone(timezone)
        first_day = requested_tz.fromutc(datetime.utcnow() + relativedelta(hours=self.min_schedule_hours))
        last_day = requested_tz.fromutc(datetime.utcnow() + relativedelta(days=self.max_schedule_days))

        # Compute available slots (ordered)
        if product:
            slots = self._product_slots_generate(first_day.astimezone(appt_tz), last_day.astimezone(appt_tz), timezone, product)
        else:
            slots = []
        # if not product or product in self.product_ids:
        #     self._check_product_booking_time(product)
            # self._slots_available(slots, first_day.astimezone(pytz.UTC), last_day.astimezone(pytz.UTC), product)

        # Compute calendar rendering and inject available slots
        today = requested_tz.fromutc(datetime.utcnow())
        start = today
        month_dates_calendar = cal.Calendar(0).monthdatescalendar
        months = []
        while (start.year, start.month) <= (last_day.year, last_day.month):
            dates = month_dates_calendar(start.year, start.month)
            for week_index, week in enumerate(dates):
                for day_index, day in enumerate(week):
                    mute_cls = weekend_cls = today_cls = None
                    today_slots = []
                    if day.weekday() in (cal.SUNDAY, cal.SATURDAY):
                        weekend_cls = 'o_weekend'
                    if day == today.date() and day.month == today.month:
                        today_cls = 'o_today'
                    if day.month != start.month:
                        mute_cls = 'text-muted o_mute_day'
                    else:
                        # slots are ordered, so check all unprocessed slots from until > day
                        while slots and (slots[0][timezone][0].date() <= day):
                            if (slots[0][timezone][0].date() == day):
                                today_slots.append({
                                    'product_id': product.id,
                                    'datetime': slots[0][timezone][0].strftime('%Y-%m-%d %H:%M:%S'),
                                    'hours': slots[0][timezone][0].strftime('%H:%M')
                                })
                            slots.pop(0)
                    dates[week_index][day_index] = {
                        'day': day,
                        'slots': today_slots,
                        'mute_cls': mute_cls,
                        'weekend_cls': weekend_cls,
                        'today_cls': today_cls
                    }

            months.append({
                'month': format_datetime(start, 'MMMM Y', locale=get_lang(self.env).code),
                'weeks': dates
            })
            start = start + relativedelta(months=1)
        # print(months)
        return months

    def _get_paginated_product_booking_slots(self, timezone, product=None, month=0):
        booking_slots = self._get_product_booking_slots(timezone, product)
        try:
            return [booking_slots[month], booking_slots[month + 1]]
        except IndexError:
            return []

    def _product_slots_generate(self, first_day, last_day, timezone, product):
        """ Generate all booking slots (in naive UTC, booking timezone, and given (visitors) timezone)
            between first_day and last_day (datetimes in booking timezone)

            :return: [ {'slot': slot_record, <timezone>: (date_start, date_end), ...},
                      ... ]
        """
        def append_slot(day, slot, product):
            local_start = appt_tz.localize(
                datetime.combine(day, time(hour=int(slot.hour), minute=int(round((slot.hour % 1) * 60)))))
            local_end = appt_tz.localize(
                datetime.combine(day,
                                 time(hour=int(slot.hour), minute=int(round((slot.hour % 1) * 60)))) + relativedelta(
                    hours=self.booking_duration))

            booked_slots = []
            for event in product.calendar_event_id:
                event_start_datetime = event.start.astimezone(requested_tz)
                event_stop_datetime = event.stop.astimezone(requested_tz)
                time_range = pandas.date_range(event_start_datetime, event_stop_datetime, freq='H', tz=None)
                booked_slots.extend([xrange for xrange in time_range])

            if local_start not in set(booked_slots):
                slots.append({
                    self.booking_tz: (
                        local_start,
                        local_end,
                    ),
                    timezone: (
                        local_start.astimezone(requested_tz),
                        local_end.astimezone(requested_tz),
                    ),
                    'UTC': (
                        local_start.astimezone(pytz.UTC).replace(tzinfo=None),
                        local_end.astimezone(pytz.UTC).replace(tzinfo=None),
                    ),
                    'slot': slot,
                })

        appt_tz = pytz.timezone(self.booking_tz)
        requested_tz = pytz.timezone(timezone)

        slots = []
        for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == first_day.isoweekday()):
            if slot.hour > first_day.hour + first_day.minute / 60.0:
                append_slot(first_day.date(), slot, product)
        slot_weekday = [int(weekday) - 1 for weekday in self.slot_ids.mapped('weekday')]
        for day in rrule.rrule(rrule.DAILY,
                               dtstart=first_day.date() + timedelta(days=1),
                               until=last_day.date(),
                               byweekday=slot_weekday):
            for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == day.isoweekday()):
                append_slot(day, slot, product)
        return slots


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    product_id = fields.Many2one("product.product", string="Product")
