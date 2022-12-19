import base64
import json
import pytz

from datetime import datetime
from psycopg2 import IntegrityError
from werkzeug.exceptions import BadRequest

from odoo import http, SUPERUSER_ID, _
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.ir_qweb_fields import nl2br
from odoo.addons.website_form.controllers.main import WebsiteForm


class CalendarWebsiteForm(WebsiteForm):

    def _handle_website_form(self, model_name, **kwargs):
        model_record = request.env['ir.model'].sudo().search([
            ('model', '=', model_name), ('website_form_access', '=', True)])

        if not model_record:
            return json.dumps({
                'error': _("The form's specified model does not exist")
            })

        booking_type_id = False

        if model_name == 'calendar.event':
            booking_type_id = request.params.pop('booking_type_id')
            booking_type_id = request.env['calendar.booking.type'].browse(int(booking_type_id))

        try:
            data = self.extract_data(model_record, request.params)
        # If we encounter an issue while extracting data
        except ValidationError as e:
            # I couldn't find a cleaner way to pass data to an exception
            return json.dumps({'error_fields': e.args[0]})

        # print(request.params)

        if model_name == 'calendar.event':
            # data.update({'name': 'Hello World', 'start': datetime.now(), 'stop': datetime.now()})
            data['record'].update({
                'name': _('%s with %s') % (booking_type_id.name, kwargs.get('Your Name')),
                'start': datetime.now(),
                'stop': datetime.now(),
                'booking_type_id': booking_type_id.id
            })

        print("data", data)


        try:
            id_record = self.insert_record(request, model_record, data['record'], data['custom'], data.get('meta'))
            if id_record:
                self.insert_attachment(model_record, id_record, data['attachments'])
                # in case of an email, we want to send it immediately instead of waiting
                # for the email queue to process
                if model_name == 'mail.mail':
                    request.env[model_name].sudo().browse(id_record).send()

        # Some fields have additional SQL constraints that we can't check generically
        # Ex: crm.lead.probability which is a float between 0 and 1
        # TODO: How to get the name of the erroneous field ?
        except IntegrityError:
            return json.dumps(False)

        request.session['form_builder_model_model'] = model_record.model
        request.session['form_builder_model'] = model_record.name
        request.session['form_builder_id'] = id_record

        return json.dumps({'id': id_record})
