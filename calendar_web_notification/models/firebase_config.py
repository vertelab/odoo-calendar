from matplotlib.pyplot import cla
from odoo import models, fields, api, _


class FirebaseConfig(models.Model):
    _name = 'firebase.config'
    _description = 'Firebase Config'
    _rec_name = 'firebase_project_id'

    firebase_project_id = fields.Char('Project ID', required=True)
    firebase_web_api_key = fields.Char('Web API Key', required=True)
    firebase_push_certificate_key = fields.Char('Push Certificate Key ID', required=True)
    firebase_sender_id = fields.Char('Sender ID', required=True)
    firebase_admin_key_file = fields.Binary('Key File', required=True)
