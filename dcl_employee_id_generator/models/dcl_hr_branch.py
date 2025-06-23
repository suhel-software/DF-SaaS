# dcl_hr_branch.py
from odoo import models, fields

class DclHRBranch(models.Model):
    _name = 'hr.branch'
    _description = 'HR Branch'

    name = fields.Char(string='Branch Name', required=True)
    code = fields.Char(string='Branch Code')
