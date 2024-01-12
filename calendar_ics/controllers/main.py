from odoo import http
from odoo.http import request
from urllib.request import urlopen
import urllib


class res_partner_icalendar(http.Controller):

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

    @http.route(['/partner/<int:partner>/calendar/public.ics'], type='http', auth="public", website=True)
    def icalendar_public(self, partner=None, **post):
        if partner:
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
