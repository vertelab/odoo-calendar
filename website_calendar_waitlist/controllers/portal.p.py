# -*- coding: utf-8 -*-

import werkzeug
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
    def _get_base_waitlist_domain(self):
        partner_id = request.env.user.partner_id
        user_id = request.env['res.users'].sudo().search([('partner_id', '=', partner_id.id)])
        return [('related_user_id', '=', user_id.id)]  # The correct person
    #            ('kanban_state', '!=', 'blocked'),                   # In an uncancelled event
    #            ('start', '>=', datetime.date.today())]              # That hasn't already happened

    def _get_waitlist_count(self, domain=None):
        if domain is None:
            domain = self._get_base_waitlist_domain()
        return request.env['calendar.booking.type.waitlist'].sudo().search_count(domain)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'waitlist_count' in counters:
            values['waitlist_count'] = self._get_waitlist_count()

        return values

    @http.route(['/my/waitlists', '/my/waitlists/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_waitlists(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        domain = self._get_base_waitlist_domain()
        _logger.warning("#"*999)
        _logger.warning(f"{self=} {page=} {date_begin=} {date_end=} {sortby=} {kw=}")
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date asc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        task_count = self._get_waitlist_count(domain)
        # pager
        pager = portal_pager(
            url="/my/waitlists",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=task_count,
            page=page,
            step=self._items_per_page
        )
        _logger.warning(f"{domain=} {order=}")
        tasks = request.env["calendar.booking.type.waitlist"].sudo().search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_bookings_history'] = tasks.ids[:100]
        _logger.warning(f"{tasks=}")
        values.update({
            'date': date_begin,
            'date_end': date_end,
            'waitlists': tasks,
            'page_name': 'booking',
            'default_url': '/my/waitlists',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby
        })
        _logger.warning(f"{values=}")
        _logger.warning("*"*999)
        return request.render("website_calendar_waitlist.portal_my_waitlists", values)

    @http.route(['/my/waitlists/cancel'], type='http', auth="user", website=True)
    def remove_waitlist(self, waitlist_id=None, **kw):
        waitlist_id = int(waitlist_id) if waitlist_id else None
        for waitlist in request.env["calendar.booking.type.waitlist"].sudo().search(self._get_base_waitlist_domain()):
            if waitlist_id == waitlist.id:
                waitlist.unlink()
                break
        return werkzeug.utils.redirect('/my/waitlists', 307)

