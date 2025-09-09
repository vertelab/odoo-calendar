from odoo import models, fields, api


class RentalPrice(models.Model):
    _inherit = "rental.price"

    unit_type = fields.Selection(selection_add=[
        ('minutes', 'Minutes'),
        ('hour', 'Hourly'),
        ('day', 'Daily'),
        ('week', 'Weekly'),
        ('month', 'Monthly')
    ], string="Unit Duration", readonly=False, store=True)