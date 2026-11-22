from odoo import http
from odoo.http import request
from urllib.request import urlopen
import urllib


class res_partner_icalendar(http.Controller):
#        http://partner/<res.partner>/calendar/[private.ics|freebusy.ics|public.ics]
     #~ simple_blog_list = request.env['blog.post'].sudo().search([('blog_id', '=', simple_blog.id)], order='message_last_post desc')

    #~ @http.route(['/partner/<model("res.partner"):partner>/calendar/private.ics'], type='http', auth="public", website=True)
    #~ def icalendar_private(self, partner=False, **post):
        #~ if partner:
            #~ document = partner.sudo().get_ics_calendar(type='private').to_ical()
            #~ return request.make_response(
                #~ headers=[('WWW-Authenticate', 'Basic realm="MaxRealm"')]
            #~ )
        #~ else:
            #~ raise Warning("Private failed")
            #~ pass # Some error page

    @http.route(['/partner/<model("res.partner"):partner>/calendar/freebusy.ics'], type='http', auth="public", website=True)
    def icalendar_freebusy(self, partner=False, **post):
        if partner:
            #~ raise Warning("Public successfull %s" % partner.get_ics_calendar(type='public').to_ical())
            #~ return partner.get_ics_calendar(type='public').to_ical()
            document = partner.sudo().get_ics_calendar(type='freebusy').to_ical()
            return request.make_response(
                document,
                headers=[
                    ('Content-Disposition', 'attachment; filename="freebusy.ifb"'),
                    ('Content-Type', 'text/calendar'),
                    ('Content-Length', len(document)),
                ]
            )
        else:
            raise Warning()
            pass # Some error page

#    @http.route(['/partner/<model("res.partner"):partner>/calendar/public.ics'], type='http', auth="public", website=True)
    @http.route(['/partner/<int:partner>/calendar/public.ics'], type='http', auth="public", website=True)
    def icalendar_public(self, partner=None, **post):
        if partner:
            #~ raise Warning("Public successfull %s" % partner.get_ics_calendar(type='public').to_ical())
            #~ return partner.sudo().get_ics_calendar(type='public')
            document = request.env['res.partner'].sudo().browse(partner).get_ics_calendar(type='public')
            return request.make_response(
                document,
                headers=[
                    ('Content-Disposition', 'attachment; filename="public.ics"'),
                    ('Content-Type', 'text/calendar'),
                    ('Content-Length', len(document)),
                ]
            )
        else:
            raise Warning("Public failed")
            pass # Some error page