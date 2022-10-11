{
    'name': 'Calendar: Product Booking Checkout',
    'version': '14.0.0.0.1',
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
        "views/templates.xml",
        "views/sale_order_view.xml",
        "views/product_view.xml",

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}