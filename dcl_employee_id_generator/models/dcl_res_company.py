from odoo import models, fields

class DclResCompany(models.Model):
    _inherit = 'res.company'

    company_code = fields.Char(string="Company Code")
