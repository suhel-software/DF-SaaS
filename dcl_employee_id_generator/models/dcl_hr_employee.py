from odoo import models, fields, api
from odoo.exceptions import UserError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    branch_id = fields.Many2one('hr.branch', string="Branch")
    section_id = fields.Many2one('hr.section', string="Section")
    employee_id = fields.Char(string='Employee ID', readonly=True, copy=False)
    allow_generate_employee_id = fields.Boolean(string="Allow Employee ID Generation", default=False)

    @api.onchange('section_id')
    def _onchange_section(self):
        if self.section_id:
            self.department_id = self.section_id.department_id

    def action_generate_employee_id(self):
        for employee in self:
            if employee.employee_id:
                raise UserError("Employee ID is already generated.")
            if not employee.allow_generate_employee_id:
                raise UserError("Employee ID generation is not allowed.")

            branch_code = employee.branch_id.code or ''
            section_code = employee.section_id.code or ''
            department_code = employee.section_id.department_id.code or '' if employee.section_id.department_id else ''
            sequence = self.env['ir.sequence'].next_by_code('dcl.employee.id') or ''

            generated_id = f"{department_code}{section_code}{branch_code}{sequence}"
            employee.employee_id = generated_id
            employee.allow_generate_employee_id = False

            self.env['hr.employee.id.list'].create({
                'employee_id_ref': employee.id,
            })

class HrEmployeeIDList(models.Model):
    _name = 'hr.employee.id.list'
    _description = 'Employee ID List'

    employee_id_ref = fields.Many2one('hr.employee', string="Employee")
    employee_name = fields.Char(related='employee_id_ref.name', store=True)
    employee_generated_id = fields.Char(related='employee_id_ref.employee_id', store=True)
    employee_section = fields.Many2one(related='employee_id_ref.section_id', string="Section", store=True)
    employee_department = fields.Many2one(related='employee_id_ref.department_id', string="Department", store=True)

    def name_get(self):
        result = []
        for record in self:
            name = record.employee_name or 'Employee ID Record'
            result.append((record.id, name))
        return result