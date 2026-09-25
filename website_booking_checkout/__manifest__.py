{
    'name': 'Calendar: Product Booking Checkout',
    'version': '18.0.1.0.0',
    'summary': 'Product Booking Checkout.',
    'category': 'Calendar',
    'description': '''
Product Booking Checkout
========================

    Allow items to be booked via webshop
            -------------------------------------------------------

    Features:

        - Web integration: Exposes HTTP endpoints for external systems.
        - UI Integration: Extends 3 view(s) in the Odoo interface.
        - Extends Odoo: Builds on calendar.booking.type, calendar.event, product.product, product.template.
    ''',
    'sequence': '131',
    'author': 'Vertel Sverige AB',
    'website': 'https://vertel.se/apps/odoo-calendar/website_booking_checkout',
    'images': ['static/description/banner.png'],  # 560x280 px.
    'license': 'AGPL-3',
    'maintainer': 'Vertel AB',
    'repository': 'https://github.com/vertelab/odoo-calendar',
    'depends': ['product', 'website_calendar_ce', 'website_sale'],
    'data': [
        "security/ir.model.access.csv",
        "views/templates.xml",
        "views/sale_order_view.xml",
        "views/product_view.xml",

    ],
    'assets': {
        'web.assets_frontend': [
            'website_booking_checkout/static/src/js/website_calendar_ce.js'
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
