from openerp import models, fields, api, _

class res_partner_phonecall_wizard(models.TransientModel):
    _name = 'res.partner.phonecall.wizard'
    _description = 'Res Partner Phonecall Wizard'

    call_summary = fields.Char(string='Call Summary')
    partner_ids = fields.One2many(comodel_name='res.partner', compute='_get_partner_ids')

    def _get_partner_ids(self):
        self.partner_ids = self._context.get('active_ids', [])

    @api.multi
    def create_summary(self):
        for r in self:
            for p in r.partner_ids:
                r.env['crm.phonecall'].create({
                    'name': r.call_summary,
                    'partner_id': p.id,
                })
        return{
            'type': 'ir.actions.act_window',
            'res_model': 'crm.phonecall',
            'views': [(False, 'tree')],
            'target': 'current',
        }
