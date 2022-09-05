from odoo import models, fields, api, _
from pytz import timezone
from odoo.exceptions import except_orm, Warning, RedirectWarning
from datetime import datetime, timedelta, time
from time import strptime, mktime, strftime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import re

from odoo import http
from odoo.http import request
from urllib.request import urlopen
import urllib

import logging
_logger = logging.getLogger(__name__)

try:
    from icalendar import Calendar, Event, vDatetime, FreeBusy
except ImportError:
    raise Warning('icalendar library missing, pip install icalendar')


class res_partner(models.Model):
    _inherit = "res.partner"
    
    ics_url  = fields.Char(string='Url',required=False)
    ics_active = fields.Boolean(string='Active',default=False)
    ics_nextdate = fields.Datetime(string="Next")
    #~ ics_frequency = fields.Integer(string="Frequency",default=60, help="Frequency in minutes, 60 = every hour, 1440 once per day, 10080 week, 43920 month, 131760 quarterly")
    ics_frequency = fields.Selection([('15', 'Every fifteen minutes'), ('60', 'Every hour'), ('360', 'Four times a day'), ('1440', 'Once per day'), ('10080', 'Once every week'), ('43920', 'Once every month'), ('131760', 'Once every third month')], string='Frequency', default='60')
    ics_class = fields.Selection([('private', 'Private'), ('public', 'Public'), ('confidential', 'Public for Employees')], string='Privacy', default='private')
    ics_show_as = fields.Selection([('free', 'Free'), ('busy', 'Busy')], string='Show Time as')
    ics_location = fields.Char(string='Location', help="Location of Event")
    ics_allday = fields.Boolean(string='All Day')
    ics_url_field = fields.Char(string='URL to the calendar', compute='create_ics_url')

    def create_ics_url(self):
        self.ics_url_field = '%s/partner/%s/calendar/public.ics' % (self.env['ir.config_parameter'].sudo().get_param('web.base.url'), self.id)

    def ics_cron_job(self):
        for ics in self.env['res.partner'].browse(self.env['res.partner'].search([('ics_active','=',True)])):
            if not ics.ics_nextdate or (ics.ics_nextdate < fields.Datetime.today()):
                ics.get_ics_events()
                ics.ics_nextdate = fields.Datetime.to_string(fields.Datetime.from_string(ics.ics_nextdate or fields.Datetime.now()) + timedelta(minutes=int(ics.ics_frequency)))
                _logger.info('Cron job for %s done' % ics.name)

    def rm_ics_events(self):
        self.env['calendar.event'].search(['&',('partner_ids','in',self.id),('ics_subscription','=',True)]).unlink()

    def get_ics_events(self):
        if (self.ics_url):
            try:
                res = urlopen(self.ics_url).read()
            except urllib.error.HTTPError as e:
                _logger.error('ICS a %s %s' % (e.code, e.reason))
                return False
            except urllib.error.URLError as e:
                _logger.error('ICS c %s %s' % (e.code, e.reason))
                return False
            _logger.debug('ICS %s' % res)

            self.env['calendar.event'].search(['&',('partner_ids','in',self.id),('ics_subscription','=',True)]).unlink()
            #~ for event in self.env['calendar.event'].search([('ics_id','=',self.id)]):
                #~ event.unlink()
                
            self.env['calendar.event'].set_ics_event(res, self)

    def get_attendee_ids(self, event):
        #~ raise Warning('get_attendee_ids run')
        partner_ids = []
        #~ attendee_mails = []
        event_attendee_list = event.get('attendee')
        if event_attendee_list:
            if not (type(event_attendee_list) is list):
                event_attendee_list = [event_attendee_list]
            
            for vAttendee in event_attendee_list:
                _logger.debug('Attendee found %s' % vAttendee)
                attendee_mailto = re.search('(:MAILTO:)([a-zA-Z0-9_@.\-]*)', vAttendee)
                attendee_cn = re.search('(CN=)([^:]*)', vAttendee)
                if attendee_mailto:
                    attendee_mailto = attendee_mailto.group(2)
                if attendee_cn:
                    attendee_cn = attendee_cn.group(2)
                elif not attendee_mailto and not attendee_cn:
                    attendee_cn = vAttendee
                _logger.debug('Attendee found %s' % attendee_cn)
                
                #~ raise Warning('%s %s' % (vAttendee, attendee_cn))
                if attendee_mailto:
                    partner_result = self.env['res.partner'].search([('email','=',attendee_mailto)])
                    
                    if not partner_result:
                        partner_id = self.env['res.partner'].create({
                            'email': attendee_mailto,
                            'name': attendee_cn or attendee_mailto,
                            })
                    else:
                        partner_id = partner_result[0]
                elif attendee_cn:
                    partner_result = self.env['res.partner'].search([('name','=',attendee_cn)])
                    
                    if not partner_result:
                        partner_id = self.env['res.partner'].create({
                            'name': attendee_cn or attendee_mailto,
                            })
                    else:
                        partner_id = partner_result[0]
                
                #~ self.env['calendar.attendee'].create({
                    #~ 'event_id': event_id.id,
                    #~ 'partner_id': partner_id.id or None,
                    #~ 'email': attendee_mailto or '',
                    #~ })
                        
                partner_ids.append(partner_id.id or None)
                #~ attendee_mails.append(attendee_mailto or '')
                
            return partner_ids
            #~ return [partner_ids, attendee_mails]
            
    def get_ics_calendar(self,type='public'):
        calendar = Calendar()
        if type == 'private':
            for event in self.env['calendar.event'].search([('partner_ids','in',self.id)]):
                calendar.add_component(event.get_ics_file())
        elif type == 'freebusy':
            fc = FreeBusy()
            
            organizer_add = self.name and ('CN=' + self.name) or ''
            if self.name and self.email:
                organizer_add += ':'
            organizer_add += self.email and ('MAILTO:' + self.email) or ''
            fc['organizer'] = organizer_add

            for event in self.env['calendar.event'].search([('partner_ids','in',self.id)]):
                fc.add('freebusy', event.get_ics_freebusy(), encode=0)
            #~ fb.add_component(fc)
            return fc
        elif type == 'public':
            #~ raise Warning(self.env['calendar.event'].search([('partner_ids','in',self.id)]))
            exported_ics = []
            for event in reversed(self.env['calendar.event'].search([('partner_ids','in',self.id)])):
                temporary_ics = event.get_ics_file(exported_ics, self)
                if temporary_ics:
                    exported_ics.append(temporary_ics[1])
                    #~ temporary_ics[0].add('url', self.ics_url_field, encode=0)
                    calendar.add_component(temporary_ics[0])
                    #~ calendar.add('vevent', temporary_ics[0], encode=0)
            
                #~ for attendees in event.attendee_ids:
                    #~ calendar.add('attendee', event.get_event_attendees(attendees), encode=0)
                    
        tmpCalendar = calendar.to_ical().decode("utf-8")
        tmpSearch = re.findall('RRULE:[^\n]*\\;[^\n]*', tmpCalendar)
        
        for counter in range(len(tmpSearch)):
            tmpCalendar = tmpCalendar.replace(tmpSearch[counter], tmpSearch[counter].replace('\\;', ';', tmpSearch[counter].count('\\;')))
        
        #~ raise Warning(tmpCalendar)
        
        return tmpCalendar
        
    def ics_mail(self):
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        #~ raise Warning("%s compose_form" % compose_form)
        mail= self.env['mail.compose.message'].create({
            'template_id':self.env.ref('calendar_ics.email_ics_url').id, 
            'model': 'res.partner',
            'res_id': self.id,
            })
        mail.write(mail.onchange_template_id( # gets defaults from template
                                self.env.ref('calendar_ics.email_ics_url').id, mail.composition_mode,
                                mail.model, mail.res_id
                            )['value'])
        return {
                'name': _('Compose Email'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'res_id':mail.id,
                'views': [(compose_form.id, 'form')],
                'view_id': compose_form.id,
                'target': 'new',
                }

        # return {'value': {'partner_id': False}, 'warning': {'title': 'Hello', 'message': 'Hejsan'}}
 
        
        #~ ics['freebusy'] = '%s/%s' % (ics_datetime(event.start, event.allday), ics_datetime(event.stop, event.allday))

    # vtodo, vjournal, vfreebusy


  #~ eventprop  = *(

             #~ ; the following are optional,
             #~ ; but MUST NOT occur more than once

             #~ class / created / description / dtstart / geo /
             #~ last-mod / location / organizer / priority /
             #~ dtstamp / seq / status / summary / transp /
             #~ uid / url / recurid /

             #~ ; either 'dtend' or 'duration' may appear in
             #~ ; a 'eventprop', but 'dtend' and 'duration'
             #~ ; MUST NOT occur in the same 'eventprop'

             #~ dtend / duration /

             #~ ; the following are optional,
             #~ ; and MAY occur more than once

             #~ attach / attendee / categories / comment /
             #~ contact / exdate / exrule / rstatus / related /
             #~ resources / rdate / rrule / x-prop

             #~ )
