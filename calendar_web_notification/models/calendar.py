from odoo import models, fields, api, _


class Calendar(models.Model):
    _inherit = 'calendar.event'


    @api.model
    def create(self, vals):
        res = super(Calendar, self).create(vals)
        if res.partner_ids:
            self.env['res.users'].search([('partner_id', 'in', res.partner_ids.ids)]).notify_info(message='New event: %s' % res.name)
        return res