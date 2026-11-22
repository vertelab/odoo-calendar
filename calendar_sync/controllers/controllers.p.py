# -*- coding: utf-8 -*-
from odoo import http
import logging

_logger = logging.getLogger(__name__)

class CalendarSync(http.Controller):
    @http.route('/calendar_sync/', auth='public')
    def index(self, **kw):
        _logger.error(f'{self=}')
        _logger.error(f'{kw=}')
        return "Hello, world"
#        return http.request.render("calendar_sync.index", {
#            'test': "Hello, world",
#        })

#     @http.route('/sync_calendar/sync_calendar/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('sync_calendar.listing', {
#             'root': '/sync_calendar/sync_calendar',
#             'objects': http.request.env['sync_calendar.sync_calendar'].search([]),
#         })

#     @http.route('/sync_calendar/sync_calendar/objects/<model("sync_calendar.sync_calendar"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sync_calendar.object', {
#             'object': obj
#         })
