# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution, third party addon
#    Copyright (C) 2004-2016 Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, fields, api, _
from pytz import timezone
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, time
from time import strptime, mktime, strftime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import re

from odoo import http
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)

try:
    from icalendar import Calendar, Event, vDatetime, FreeBusy, Alarm
except ImportError:
    raise Warning('icalendar library missing, pip install icalendar')


# calendar_ics -> res.partner

# http://ical.oops.se/holidays/Sweden/-1,+1
# http://www.skatteverketkalender.se/skvcal-manadsmoms-maxfyrtiomiljoner-ingenperiodisk-ingenrotrut-verk1.ics

class calendar_event(models.Model):
    _inherit = 'calendar.event'

    ics_subscription = fields.Boolean(default=False)  # partner_ids + ics_subscription -> its ok to delete

    def set_ics_event(self, ics_file, partner):
        for event in Calendar.from_ical(ics_file).walk('vevent'):

            summary = ''
            description = event.get('description', '')
            if event.get('summary') and len(event.get('summary')) < 35:
                summary = event.get('summary')
            elif len(event.get('summary')) >= 35:
                summary = event.get('summary')[:35]
                if not event.get('description'):
                    description = event.get('summary')

            record = {r[1]: r[2] for r in [
                ('dtstart', 'start_date', event.get('dtstart') and event.get('dtstart').dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                ('dtend', 'stop_date', event.get('dtend') and event.get('dtend').dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                ('duration', 'duration', event.get('duration')),
                ('location', 'location', event.get('location') and event.get('location') or partner.ics_location),
                ('summary', 'name', summary),
                ('rrule', 'rrule', event.get('rrule') and event.get('rrule').to_ical() or None),
            ] if event.get(r[0])}

            partner_ids = self.env['res.partner'].get_attendee_ids(event)

            if partner_ids:
                partner_ids.append(partner.id)
            else:
                partner_ids = [partner.id]

            record['partner_ids'] = [(6, 0, self.env['res.partner'].browse(partner_ids).ids)]

            record['ics_subscription'] = True
            record['start'] = record.get('start_date')
            record['stop'] = record.get('stop_date') or record.get('start')
            record['description'] = description
            record['show_as'] = partner.ics_show_as
            record['allday'] = partner.ics_allday

            tmpStart = datetime.time(
                datetime.fromtimestamp(mktime(strptime(record['start'], DEFAULT_SERVER_DATETIME_FORMAT))))
            tmpStop = datetime.fromtimestamp(mktime(strptime(record['stop'], DEFAULT_SERVER_DATETIME_FORMAT)))

            if tmpStart == time(0, 0, 0) and tmpStart == datetime.time(tmpStop):
                record['allday'] = True

            if not record.get('stop_date'):
                record['allday'] = True
                record['stop_date'] = record['start_date']
            elif record.get('stop_date') and record['allday']:
                record['stop_date'] = vDatetime(tmpStop - timedelta(hours=24)).dt.strftime(
                    DEFAULT_SERVER_DATETIME_FORMAT)
                record['stop'] = record['stop_date']
            record['show_as'] = 'free'
            _logger.error('ICS %s' % record)
            self.env['calendar.event'].create(record)

    def get_ics_event(self):
        event = self[0]
        ics = Event()
        ics = self.env['calendar.attendee'].get_ics_file(event)
        calendar = Calendar()
        date_format = DEFAULT_SERVER_DATETIME_FORMAT

        return ics

    def get_ics_file(self, events_exported, partner):
        """
        Returns iCalendar file for the event invitation.
        @param event: event object (browse record)
        @return: .ics file content
        """
        ics = Event()
        event = self[0]

        def ics_datetime(idate, allday=False):
            if type(idate) in (datetime, datetime.date):
                idate = idate.strftime("%Y-%m-%d %H:%M:%S")
            if idate:
                # if allday:
                #     return str(vDatetime(
                #         datetime.fromtimestamp(mktime(strptime(idate, DEFAULT_SERVER_DATETIME_FORMAT)))).to_ical())[:8]
                # else:
                return vDatetime(datetime.fromtimestamp(
                    mktime(strptime(idate, DEFAULT_SERVER_DATETIME_FORMAT)))).to_ical().decode("utf-8") + 'Z'
            return False

        if not event.start or not event.stop:
            raise ValidationError(_('Warning!'), _("First you have to specify the date of the invitation."))
        ics['summary'] = event.name
        if event.description:
            ics['description'] = event.description
        if event.location:
            ics['location'] = event.location
        if event.rrule:
            ics['rrule'] = event.rrule

        if event.alarm_ids:
            for alarm in event.alarm_ids:
                if alarm.type == 'notification':
                    valarm = Alarm()
                    valarm.add('ACTION', 'DISPLAY')
                    if alarm.interval == 'days':
                        delta = timedelta(days=alarm.duration)
                    elif alarm.interval == 'hours':
                        delta = timedelta(hours=alarm.duration)
                    elif alarm.interval == 'minutes':
                        delta = timedelta(minutes=alarm.duration)
                    trigger = valarm.add('TRIGGER', -delta)
                    valarm.add('DESCRIPTION', event.name)
                    ics.add_component(valarm)
        if event.attendee_ids:
            for attendee in event.attendee_ids:
                attendee_add = ics.get('attendee')
                attendee_add = attendee.common_name and ('CN=' + attendee.common_name) or ''
                if attendee.common_name and attendee.email:
                    attendee_add += ':'
                attendee_add += attendee.email and ('MAILTO:' + attendee.email) or ''

                ics.add('attendee', attendee_add, encode=0)

        if events_exported:
            event_not_found = True

            for event_comparison in events_exported:
                if str(ics) == event_comparison:
                    event_not_found = False
                    break

            if event_not_found:
                events_exported.append(str(ics))

                ics['uid'] = '%s@%s-%s' % (event.id, self.env.cr.dbname, partner.id)
                ics['created'] = ics_datetime(strftime(DEFAULT_SERVER_DATETIME_FORMAT))
                tmpStart = ics_datetime(event.start, event.allday)
                tmpEnd = ics_datetime(event.stop, event.allday)

                ics['dtstart'] = tmpStart

                ics['dtend'] = tmpEnd

                # if event.allday:
                #     ics['dtstart;value=date'] = tmpStart
                # else:
                #     ics['dtstart'] = tmpStart
                #
                # if tmpStart != tmpEnd or not event.allday:
                #     if event.allday:
                #         ics['dtend;value=date'] = str(vDatetime(datetime.fromtimestamp(
                #             mktime(strptime(event.stop, DEFAULT_SERVER_DATETIME_FORMAT))) + timedelta(
                #             hours=24)).to_ical())[:8]
                #     else:
                #         ics['dtend'] = tmpEnd

                return [ics, events_exported]

        else:
            events_exported.append(str(ics))

            ics['uid'] = '%s@%s-%s' % (event.id, self.env.cr.dbname, partner.id)
            ics['created'] = ics_datetime(strftime(DEFAULT_SERVER_DATETIME_FORMAT))
            tmpStart = ics_datetime(event.start, event.allday)
            tmpEnd = ics_datetime(event.stop, event.allday)

            ics['dtstart'] = tmpStart

            ics['dtend'] = tmpEnd

            # if event.allday:
            #     ics['dtstart;value=date'] = tmpStart
            # else:
            #     ics['dtstart'] = tmpStart
            #
            # if tmpStart != tmpEnd or not event.allday:
            #     if event.allday:
            #         ics['dtend;value=date'] = str(
            #             vDatetime(datetime.fromtimestamp(
            #                 mktime(strptime(
            #                     event.stop, DEFAULT_SERVER_DATETIME_FORMAT))) + timedelta(hours=24)).to_ical())[:8]
            #     else:
            #         ics['dtend'] = tmpEnd

            return [ics, events_exported]

    def get_ics_freebusy(self):
        """
        Returns iCalendar file for the event invitation.
        @param event: event object (browse record)
        @return: .ics file content
        """
        event = self[0]

        def ics_datetime(idate, iallday=False):
            if idate:
                return vDatetime(idate).to_ical()
            return False

        if not event.start or not event.stop:
            raise ValidationError(_('Warning!'), _("First you have to specify the date of the invitation."))

        allday = event.allday
        event_start = datetime.fromtimestamp(mktime(strptime(event.start, DEFAULT_SERVER_DATETIME_FORMAT)))
        event_stop = datetime.fromtimestamp(mktime(strptime(event.stop, DEFAULT_SERVER_DATETIME_FORMAT)))

        if allday:
            event_stop += timedelta(hours=23, minutes=59, seconds=59)

        return '%s/%s' % (ics_datetime(event_start, allday), ics_datetime(event_stop, allday))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: