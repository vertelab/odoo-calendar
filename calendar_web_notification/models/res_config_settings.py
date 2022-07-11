# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'


    firebase_config_id = fields.Many2one('firebase.config', 'Firebase Config', readonly=False, config_parameter='firebase_config_id')

    firebase_enable_push_notifications = fields.Boolean('Enable Web Push Notifications', readonly=False, config_parameter='firebase_enable_push_notifications')
    firebase_project_id = fields.Char('Project ID', readonly=False, related='firebase_config_id.firebase_project_id')
    firebase_web_api_key = fields.Char('Web API Key', readonly=False, related='firebase_config_id.firebase_web_api_key')
    firebase_push_certificate_key = fields.Char('Push Certificate Key', readonly=False, related='firebase_config_id.firebase_push_certificate_key')
    firebase_sender_id = fields.Char('Sender ID', readonly=False, related='firebase_config_id.firebase_sender_id')
    firebase_admin_key_file = fields.Binary('Key File', readonly=False, related='firebase_config_id.firebase_admin_key_file')
