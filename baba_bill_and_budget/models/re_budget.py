from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)



class JobSummaryAdditionalItem(models.Model):
    _name = 'job.summary.additional.item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Additional Item'

    job_summary_id = fields.Many2one('job.summary', string='Job Summary')
    item_name = fields.Char(string='Item Name')
    quantity = fields.Float(string='Quantity')
    unit_price = fields.Float(string='Unit Price')
    total = fields.Float(string='Total', compute='_compute_total', store=True)
    unit = fields.Selection(
        [
            ("bag", "BAG"),
            ("box", "BOX"),
            ("sft", "SFT"),
            ("cft", "CFT"),
            ("dollar", "DOLLAR"),
            ("floor", "FLOOR"),
            ("foot", "FOOT"),
            ("gm", "GM"),
            ("inch", "INCH"),
            ("kg", "KG"),
            ("liter", "LITER"),
            ("mbps", "MBPS"),
            ("ml", "ML"),
            ("node", "NODE"),
            ("package", "PACKAGE"),
            ("pair", "PAIR"),
            ("per month", "PER MONTH"),
            ("person", "PERSON"),
            ("pices", "PICES"),
            ("pkt", "PKT"),
            ("ream", "REAM"),
            ("set", "SET"),
            ("taka", "TAKA"),
            ("ton", "TON"),
            ("yards", "YARDS"),
            ("year", "YEAR"),
        ],
    )
    approved_amount = fields.Float('Approve', compute='_compute_approved_amount', inverse='_set_approved_amount',
                                   store=True)
    def _set_approved_amount(self):
        for record in self:
            record.total = record.approved_amount

    @api.depends('quantity', 'unit_price')
    def _compute_total(self):
        for record in self:
            record.total = record.quantity * record.unit_price


class JobSummaryAdditionalApprover(models.Model):
    _name = 'job.summary.additional.approver'
    _description = 'Additional Approver'

    job_summary_id = fields.Many2one('job.summary', string='Job Summary')

    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, required=True, default=lambda self: self._default_user())
    option = fields.Selection([
        ('recommendation', 'Recommendation To'),
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string='Flow')
    recommended_user_id = fields.Many2one(comodel_name="res.users", string='Recommended To', store=True)
    b_note = fields.Char("Note")
    time_of_approval = fields.Datetime(string='Time of Approval/Recommendation',
                                       default=lambda self: self._default_time_of_approval())

    @api.model
    def _default_time_of_approval(self):
        # Set the default time to Bangladesh Standard Time (BST)
        bst_timezone = pytz.timezone('Asia/Dhaka')
        current_time_utc = datetime.now(pytz.utc)
        current_time_bst = current_time_utc.astimezone(bst_timezone)
        return current_time_bst.strftime('%Y-%m-%d %H:%M:%S')

    @api.model
    def _default_user(self):
        # Assuming self.env.user is available to get the current user
        return self.env.user.id

    status_display = fields.Char(string='Status', compute='_compute_status_display', store=True, readonly=True)

    @api.depends('option')
    def _compute_status_display(self):
        for record in self:
            if record.option == 'reject':
                record.status_display = 'Rejected'
            elif record.option == 'recommendation':
                record.status_display = 'Recommended'
            elif record.option == 'approve':
                record.status_display = 'Approved'


