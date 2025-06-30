from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _,tools
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)


class RecommendationView(models.Model):
    _name = 'recommendation.view'
    _description = 'Unified Recommendation View'


class JobSummaryWizard(models.TransientModel):
    _name = 'job.summary.wizard'
    _description = 'Job Summary Wizard'


class JobSummaryItemsWizard(models.TransientModel):
    _name = 'job.summary.items.wizard'
    _description = 'Job Summary Items Wizard'


class JobSummaryApproverWizard(models.TransientModel):
    _name = 'job.summary.approver.wizard'
    _description = 'Job Summary Approver Wizard'


class BillAdjustmentAttachmentWizard(models.TransientModel):
    _name = 'bill.adjustment.attachment.wizard'
    _description = 'Bill Adjustment Attachment Wizard'

    bill_id = fields.Many2one('bill.adjustment', string='Bill Adjustment', required=True)
    file = fields.Binary('File', required=True)
    file_name = fields.Char('File Name')

    def action_upload_file(self):
        """Upload the file as an attachment and log it in the chatter."""
        if self.file:
            self.env['ir.attachment'].create({
                'name': self.file_name,
                'datas': self.file,
                'res_model': 'bill.adjustment',
                'res_id': self.bill_id.id,
            })
            # Log the attachment to the chatter
            self.bill_id.message_post(
                body='New attachment added: %s' % (self.file_name),
                attachment_ids=[self.env['ir.attachment'].search([('name', '=', self.file_name)], limit=1).id],
            )
