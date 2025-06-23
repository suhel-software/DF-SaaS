# dcl_employee_id_generator/models/dcl_hr_section.py
from odoo import models, fields

class HrSection(models.Model):
    _name = 'hr.section'
    _description = 'HR Section'

    name = fields.Char(required=True)
    code = fields.Char(string="Section Code")
    department_id = fields.Many2one('hr.department', string="Department")