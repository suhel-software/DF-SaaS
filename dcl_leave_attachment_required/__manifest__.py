# -*- coding: utf-8 -*-
{
'name': 'Leave Attachment Required  ',
'summary': 'Leave Attachment Required  , Leave, HR, Attachment, Holiday, '
           'Document, Prescription, Proof, Certificate, Sick Leave, Vacation',
'version': '14.1',
'category': 'Human Resources',
'website': 'https://www.daffodil-bd.com',
'description': ''' Leave Attachment Required  ''',
'images': "",
'author': 'IMRAN',


'installable': True,
'depends': ['hr_holidays', 'base'],
'data': ['views/dcl_hr_leave_views.xml',
        'views/dcl_hr_leave_type_views.xml',
         ],
'odoo-apps': True,
'application': False
}