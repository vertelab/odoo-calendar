# -*- coding: utf-8 -*-

import logging
import datetime

#from collections import OrderedDict

#from operator import itemgetter

from odoo import http, _
#from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
#from odoo.tools import groupby as groupbyelem

#from odoo.osv.expression import OR


_logger = logging.getLogger(__name__)


# TODO: If a non-user cancels an event, either the task or the calendar event:
# 1. The user should be notified.
# 2. The task and the calendar event should both be removed.

class CustomerPortalExtension(CustomerPortal):
    def _get_base_booking_domain(self):
        return [('partner_ids', 'in', request.env.user.partner_id.id), # The correct person
                # ~ ('kanban_state', '!=', 'blocked'),                   # In an uncancelled event
                ('start', '>=', datetime.date.today())]              # That hasn't already happened

    def _get_booking_count(self, domain=None):
        if domain is None:
            domain = self._get_base_booking_domain()
        return request.env["calendar.event"].sudo().search_count(domain)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'booking_count' in counters:
            values['booking_count'] = self._get_booking_count()

        return values

    @http.route(['/my/bookings', '/my/bookings/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_bookings(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        domain = self._get_base_booking_domain()

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'start asc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        task_count = self._get_booking_count(domain)
        # pager
        pager = portal_pager(
            url="/my/bookings",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=task_count,
            page=page,
            step=self._items_per_page
        )
        _logger.warning("#"*999)
        _logger.warning(f"{domain=} {order=}")
        # ~ tasks = request.env["project.task"].sudo().search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        # ~ domain=[('partner_id', '=', 91), ('kanban_state', '!=', 'blocked'), ('start', '>=', datetime.date(2022, 3, 4))]
        calender_booking = request.env["calendar.event"].sudo().search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_bookings_history'] = calender_booking.ids[:100]
        _logger.warning(f"{calender_booking=}")
        values.update({
            'date': date_begin,
            'date_end': date_end,
            'bookings': calender_booking,
            'page_name': 'booking',
            'default_url': '/my/bookings',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby
        })
        return request.render("website_calendar_event.portal_my_bookings", values)

