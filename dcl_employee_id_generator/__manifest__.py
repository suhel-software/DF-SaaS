{
    'name': 'DCL Employee ID Generator',
    'version': '14.0.1.0.0',
    'summary': 'Auto-generate Employee IDs using Department, Section, and Branch codes',
    'author': 'Your Company',
    'category': 'Human Resources',
    'depends': ['base', 'hr'],
    'data': [
        'data/dcl_employee_id_sequence.xml',
        'views/dcl_hr_department_views.xml',
        'views/dcl_hr_section_views.xml',
        'views/dcl_hr_branch_views.xml',
        'views/dcl_hr_employee_views.xml',
        'menus/dcl_menus_views.xml',
        'security/ir.model.access.csv',

    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}


