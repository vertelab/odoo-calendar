from . import calendar_event
from . import ir_http
from . import caldav_collection
from . import caldav_collection_field_mapping
# res_ppartner defines the model; res_partner inherits it for caldav_uuid.
# Order matters: the model must exist before the inheritance.
from . import res_ppartner
from . import res_partner
from . import mail_message
from . import project_task
