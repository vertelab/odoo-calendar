# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Enterprise Management Solution, third party addon
#    Copyright (C) 2018- Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)


class calendar_configuration(models.TransientModel):
    _inherit = 'account.config.settings'

    tax_recurrency = fields.Selection(string="Redovisar moms", selection=[('manadsmoms',u'Månatligen'),('tremandersmoms','Kvartalsvis'),('arsmomsenskild','Årsmoms Enskild näringsidkare'),('arsmomsjuridiskelektroniskt','Årsmoms juridisk person, elektroniskt'),('arsmomsjuridiskpapper','Årsmoms juridisk person papper'),('arsmomshuvudregel','Årsmoms huvudregeln')])
    revenue =  fields.Selection(string="Omsättning", selection=[('maxfyrtiomiljoner',u'Upp till 40 milj'),('plusfyrtiomiljoner','40 miljoner eller mer')])
    periodic_compilation = fields.Selection(string="Periodisk sammanställning", selection=[('ingenperiodisk',u'Nej'),('pappersperiodisk','På papper månatligen'),('elektroniskperiodisk','Elektroniskt månatligen'),('pappersperiodiskkvartal','På papper kvartalsvis'),('elektroniskperiodiskkvartal','Elektroniskt kvartalsvis')])
    rot_rut = fields.Selection(string="ROT / RUT", selection=[('ingenrotrut',u'Nej'),('rotrut','Ja')])
    fiscalyear = fields.Selection(string="Fiscal year", selection=[('verk1',u'januari - december'),('verk2','februari - januari'),('verk3','mars - februari'),('verk4','april - mars'),('verk5','maj - april'),('verk6','juni - maj'),('verk7','juli - juni'),('verk8','augusti - juli'),('verk9','september - augusti'),('verk10','oktober - augusti'),('verk11','november - oktober'),('verk12','december - november'),])
    kalender_url = fields.Char(string='Url')

    @api.onchange('tax_recurrency','revenue','periodic_compilation','rot_rut','fiscalyear')
    def _kalender_url(self):
        self.kalender_url = 'http://www.skatteverketkalender.se/skvcal-%s-%s-%s-%s-%s.ics' % (self.tax_recurrency, self.revenue, self.periodic_compilation, self.rot_rut, self.fiscalyear)
#                            http://www.skatteverketkalender.se/skvcal-tremanadersmoms-maxfyrtiomiljoner-ingenperiodisk-ingenrotrut-verk1.ics

    @api.model
    def get_default_skvkalender_values(self, fields):
        return {
            'tax_recurrency': self.env['ir.config_parameter'].get_param('skvkalender.tax_recurrency'),
            'revenue': self.env['ir.config_parameter'].get_param('skvkalender.revenue'),
            'periodic_compilation': self.env['ir.config_parameter'].get_param('skvkalender.periodic_compilation'),
            'rot_rut': self.env['ir.config_parameter'].get_param('skvkalender.rot_rut'),
            'fiscalyear': self.env['ir.config_parameter'].get_param('skvkalender.fiscalyear'),
            'kalender_url': self.env['ir.config_parameter'].get_param('skvkalender.kalender_url'),
        }

    @api.multi
    def set_skvkalender_values(self):
        for record in self:
            self.env['ir.config_parameter'].set_param(key="skvkalender.tax_recurrency", value=record.tax_recurrency)
            self.env['ir.config_parameter'].set_param(key="skvkalender.revenue", value=record.revenue)
            self.env['ir.config_parameter'].set_param(key="skvkalender.periodic_compilation", value=record.periodic_compilation)
            self.env['ir.config_parameter'].set_param(key="skvkalender.rot_rut", value=record.rot_rut)
            self.env['ir.config_parameter'].set_param(key="skvkalender.fiscalyear", value=record.fiscalyear)
            self.env['ir.config_parameter'].set_param(key="skvkalender.kalender_url", value=record.kalender_url)
            self.env.ref('l10n_se_calendar.svenska_skatteverket').ics_url = record.kalender_url

