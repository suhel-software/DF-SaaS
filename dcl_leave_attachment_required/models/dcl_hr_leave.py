from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrLeave(models.Model):
    _inherit = "hr.leave"

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_leave_attachment_rel',
        'leave_id',
        'attachment_id',
        string='Attachments',
        domain="[('res_model', '=', 'hr_leave')]"
    )

    @api.constrains('state', 'holiday_status_id')
    def _check_attachment(self):
        for record in self:
            if record.state not in ['draft', 'cancel', 'refuse'] and record.holiday_status_id.attachment_required:
                if not record.attachment_ids:
                    raise ValidationError(_('You cannot submit this leave without attaching the required document.'))
