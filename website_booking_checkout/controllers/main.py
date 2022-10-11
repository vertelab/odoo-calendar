# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from datetime import datetime, timedelta
from werkzeug.exceptions import Forbidden, NotFound
import pytz
from odoo import fields, http, SUPERUSER_ID, tools, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf

_logger = logging.getLogger(__name__)


class BookingWebsiteSale(WebsiteSale):

    @http.route([
        '/shop/<model("product.product"):product>/booking-type/'], type='http', auth="public", website=True)
    def calendar_booking_choice(self, product, booking_type=None, message=None, description=None, header=None,
                                **kwargs):
        # sale_order_id = request.session['sale_order_id']
        print(product)

        if not booking_type:
            country_code = request.session.geoip and request.session.geoip.get('country_code')
            if country_code:
                suggested_booking_types = request.env['calendar.booking.type'].search([
                    '|', ('country_ids', '=', False),
                    ('country_ids.code', 'in', [country_code])])
            else:
                suggested_booking_types = request.env['calendar.booking.type'].search([])
            if not suggested_booking_types:
                return request.render("website_calendar_ce.setup", {})
            booking_type = suggested_booking_types[0]
        else:
            suggested_booking_types = booking_type

        return request.render("website_booking_checkout.product_booking_type", {
            'booking_type': booking_type,
            'suggested_booking_types': suggested_booking_types,
            'message': message,
            'description': description,
            'header': header,
            'product': product,
        })

    @http.route(['/shop/<model("product.product"):product>/<model("calendar.booking.type"):booking_type>'], type='http',
                auth="public", website=True, sitemap=True)
    def shop_product_booking(self, product, booking_type, category='', search='', failed=False, **kwargs):
        print("booking_type", booking_type)
        booking_type = request.env['calendar.booking.type'].browse(int(booking_type))
        session = request.session
        timezone = session.get('timezone')
        if not timezone:
            timezone = session.context.get('tz')
        slot_ids = booking_type.sudo()._get_paginated_product_booking_slots(timezone, product)

        booking_values = self._prepare_product_values(product, category, search, **kwargs)
        booking_values.update({
            'booking_type': booking_type,
            'product_id': product,
            'timezone': timezone,
            'failed': failed,
            'slots': slot_ids,
            'description': _(
                "Fill your personal information in the form below, and confirm the booking. We'll send an invite to "
                "your email address"),
            'title': _("Book meeting"),
        })

        return request.render("website_booking_checkout.product_booking", booking_values)

    @http.route(['/shop/booking/update'], type='http', auth="public", website=True)
    def booking_update(self, product_id=None, start_date=None, end_date=None, booking_type_id=None, **kw):
        timezone = request.session['timezone']
        tz_session = pytz.timezone(timezone)
        sale_order_id = request.session['sale_order_id']
        start_date = tz_session.localize(fields.Datetime.from_string(start_date)).astimezone(pytz.utc)
        booking_type_id = request.env['calendar.booking.type'].browse(int(booking_type_id))
        if end_date:
            end_date = tz_session.localize(fields.Datetime.from_string(end_date)).astimezone(pytz.utc)
        if not end_date or end_date == 'undefined':
            end_date = start_date + timedelta(hours=booking_type_id.booking_duration)
        if sale_order_id and booking_type_id and start_date:
            sale_id = request.env['sale.order'].browse(int(sale_order_id))
            sale_id.write({
                'booking_type_id': booking_type_id,
                'start_date': start_date.strftime(dtf),
                'end_date': end_date.strftime(dtf),
            })
            return request.redirect("/shop/cart")
        return request.redirect("/shop")

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """This route is called when adding a product to cart (no options)."""
        sale_order = request.website.sale_get_order(force_create=True)
        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)

        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json.loads(kw.get('product_custom_attribute_values'))

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json.loads(kw.get('no_variant_attribute_values'))

        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values
        )

        if kw.get('express'):
            return request.redirect("/shop/checkout?express=1")

        # return request.redirect("/shop/cart")
        product_id = request.env["product.product"].browse(int(product_id))
        return request.redirect(f"/shop/{product_id.id}/booking-type")

    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def payment_confirmation(self, **post):
        """ End of checkout process controller. Confirmation is basically seing
        the status of a sale.order. State at this point :

         - should not have any context / session info: clean them
         - take a sale.order id, because we request a sale.order and are not
           session dependant anymore
        """
        sale_order_id = request.session.get('sale_last_order_id')
        if sale_order_id:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            self._make_booking(order)
            return request.render("website_sale.confirmation", {'order': order})
        else:
            return request.redirect('/shop')

    def _make_booking(self, sale_order):
        data = {
            'state': 'open',
            'name': _('%s with %s') % (sale_order.name, sale_order.partner_id.name),
            'start_date': sale_order.start_date.strftime(dtf),
            'start': sale_order.start_date.strftime(dtf),
            'stop': sale_order.end_date.strftime(dtf),
            'allday': False,
            'duration': sale_order.booking_type_id.booking_duration,
            'description': '',  # record_description,
            'alarm_ids': sale_order.booking_type_id.reminder_ids.ids,
            # 'location': f"https://{booking_type.meeting_base_url}/{str(uuid.uuid1())}",
            'partner_ids': [(4, sale_order.partner_id.id, False)],
            'booking_type_id': sale_order.booking_type_id.id,
            'user_id': request.env.user.id,
            'product_id': sale_order.order_line[0].product_id.id,
        }
        event = request.env['calendar.event'].sudo().with_context(
            allowed_company_ids=request.env.user.company_ids.ids).create(data)
        return event

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        """
        Main cart management + abandoned cart revival
        access_token: Abandoned cart SO access token
        revive: Revival method when abandoned cart. Can be 'merge' or 'squash'
        """
        order = request.website.sale_get_order()
        if order and order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order()
        values = {}
        if access_token:
            abandoned_order = request.env['sale.order'].sudo().search([('access_token', '=', access_token)], limit=1)
            if not abandoned_order:  # wrong token (or SO has been deleted)
                raise NotFound()
            if abandoned_order.state != 'draft':  # abandoned cart already finished
                values.update({'abandoned_proceed': True})
            elif revive == 'squash' or (revive == 'merge' and not request.session.get(
                    'sale_order_id')):  # restore old cart or merge with unexistant
                request.session['sale_order_id'] = abandoned_order.id
                return request.redirect('/shop/cart')
            elif revive == 'merge':
                abandoned_order.order_line.write({'order_id': request.session['sale_order_id']})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session.get(
                    'sale_order_id'):  # abandoned cart found, user have to choose what to do
                values.update({'access_token': abandoned_order.access_token})

        values.update({
            'website_sale_order': order,
            'start_date': fields.Datetime.context_timestamp(order, order.start_date).strftime(
                dtf) if order.start_date else False,
            'end_date': fields.Datetime.context_timestamp(order, order.end_date).strftime(
                dtf) if order.end_date else False,
            'date': fields.Date.today(),
            'suggested_products': [],
        })
        if order:
            order.order_line.filtered(lambda l: not l.product_id.active).unlink()
            _order = order
            if not request.env.context.get('pricelist'):
                _order = order.with_context(pricelist=order.pricelist_id.id)
            values['suggested_products'] = _order._cart_accessories()

        if post.get('type') == 'popover':
            # force no-cache so IE11 doesn't cache this XHR
            return request.render("website_sale.cart_popover", values, headers={'Cache-Control': 'no-cache'})

        if order.order_line and not order.start_date:
            return request.redirect(f"/shop/{order.order_line[0].product_id.id}/booking-type")

        return request.render("website_sale.cart", values)

    @http.route(['/product-booking-slots'], type='json', auth="public", website=True)
    def toggle_product_booking_slots(self, booking_type=None, product_id=None, month=0, description=None, title=None,
                                     **kwargs):
        booking_type = request.env['calendar.booking.type'].sudo().browse(int(booking_type)) if booking_type else None
        request.session['timezone'] = booking_type.booking_tz
        product_product_id = request.env['product.product'].sudo().browse(int(product_id)) if product_id else None
        slot_ids = booking_type.sudo()._get_paginated_product_booking_slots(
            request.session['timezone'], product_product_id, int(month))

        if slot_ids:
            return request.env['ir.ui.view']._render_template("website_booking_checkout.product_booking_calendar", {
                'booking_type': booking_type,
                'product': product_product_id,
                'timezone': request.session['timezone'],
                'slots': slot_ids,
                'description': description if description else _(
                    "Fill your personal information in the form below, and confirm the booking. We'll send an invite "
                    "to your email address"),
                'title': title if title else _("Book meeting"),
            })
        else:
            return False

    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=True)
    def product(self, product, category='', search='', **kwargs):
        if not product.can_access_from_current_website():
            raise NotFound()
        order = request.website.sale_get_order()

        if order and order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order()
        product_values = self._prepare_product_values(product, category, search, **kwargs)
        if order.order_line:
            product_values.update({
                'product_on_order': order.order_line[0].product_id,
                'has_products': True
            })

        return request.render("website_sale.product", product_values)

    @http.route(['/shop/checkout'], type='http', auth="public", website=True, sitemap=False)
    def checkout(self, **post):
        order = request.website.sale_get_order()

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            return request.redirect('/shop/address')

        redirection = self.checkout_check_address(order)
        if redirection:
            return redirection

        values = self.checkout_values(**post)

        if post.get('express'):
            return request.redirect('/shop/confirm_order')

        values.update({'website_sale_order': order})

        # Avoid useless rendering if called in ajax
        if post.get('xhr'):
            return 'ok'

        if order.order_line and not order.start_date:
            return request.redirect(f"/shop/{order.order_line[0].product_id}/booking-type")
        return request.render("website_sale.checkout", values)
