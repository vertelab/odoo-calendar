# -*- coding: utf-8 -*-
{
    'name': "Import holidays",
    'version': "1.0",
    'depends': [
        'calendar', 
        'hr',
    ],
    'description': """
    This is a module you can use to import holidays into the calendar and the resource calendar.
    Currently it only allows for one URL containing an .ics file to be imported. 
    It updates monthly for new holidays so that you are always up to date.

    Required python library: 'ics', just do "pip install ics" on your machine and you should be able to install it
    """,
    'data': [
        "views/res_config_settings.xml",
        #"security/ir.model.access.csv",
    ],
    'external_dependencies': {
    'python': ['ics'],
    },
}
