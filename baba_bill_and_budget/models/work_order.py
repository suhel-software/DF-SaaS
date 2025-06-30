from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)

class WorkOrder(models.Model):
    _name = 'work.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Work Order No'

    name = fields.Char('Work Order Number')
    work_order_number = fields.Char('Work Order Name')
    cost_center_id = fields.Many2one('job.center', string='Cost Center')
    job_create_id = fields.Many2one('job.create', string='Budget Name',
                                    domain="[('job_center_id', '=', cost_center_id)]")
    term_condition = fields.Text('Term And Condition')
    vendor_name = fields.Many2one(comodel_name="res.partner", string='Vendor Name',
                                  store=True, )
    note = fields.Text('Note')
    attachment_file = fields.Binary('Attachment File')
    attachment_filename = fields.Char('File Name')
    url_link = fields.Char('URL Link', help='Enter a URL to link to a site', widget="url")

    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('items.total')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = sum(record.items.mapped('total'))

    items = fields.One2many('work.order.items', 'summary_id', string='Items')


class WorkOrderItems(models.Model):
    _name = 'work.order.items'
    _description = 'Work Order Items'

    summary_id = fields.Many2one('work.order', string='Work Order Summary')
    name = fields.Char('Name')
    item_name = fields.Char('Item Name')
    quantity = fields.Float('Quantity')
    unit_price = fields.Float('Unit Price')
    total = fields.Float('Total', compute='_compute_total', store=True)
    # approved_amount = fields.Float('Approve')
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

    @api.depends('quantity', 'unit_price')
    def _compute_total(self):
        for record in self:
            record.total = record.quantity * record.unit_price
