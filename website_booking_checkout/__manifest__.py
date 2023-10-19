{
    'name': 'Calendar: Product Booking Checkout',
    'version': '16.0.0.0.1',
    'summary': 'Product Booking Checkout',
    'category': 'Calendar',
    'description': """
        Allow items to be booked via webshop
        -------------------------------------------------------
    """,
    'sequence': '131',
    'author': 'Vertel AB',
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