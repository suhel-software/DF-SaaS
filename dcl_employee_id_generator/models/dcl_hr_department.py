# dcl_employee_id_generator/models/dcl_hr_department.py
from odoo import models, fields

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    code = fields.Char(string="Department Code")