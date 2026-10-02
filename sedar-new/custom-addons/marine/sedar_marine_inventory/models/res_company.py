from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


OFFICER_GROUP = "sedar_marine_inventory.group_marine_inventory_manager"


class ResCompany(models.Model):
    _inherit = "res.company"

    sedar_procurement_inventory_officer_id = fields.Many2one(
        "res.users",
        string="Procurement and Inventory Officer",
        domain="[('active', '=', True), ('share', '=', False)]",
        help="The exact employee authorized to control procurement and inventory for this company.",
    )
    sedar_default_storage_location_id = fields.Many2one(
        "stock.location",
        string="Default SEDAR Storage Location",
        ondelete="restrict",
    )
    sedar_consumption_location_id = fields.Many2one(
        "stock.location",
        string="SEDAR Consumption Location",
        ondelete="restrict",
    )
    sedar_disposal_location_id = fields.Many2one(
        "stock.location",
        string="SEDAR Disposal Location",
        ondelete="restrict",
    )

    @api.constrains("sedar_procurement_inventory_officer_id")
    def _check_sedar_procurement_inventory_officer(self):
        for company in self:
            officer = company.sedar_procurement_inventory_officer_id
            if not officer:
                continue
            if not officer.active or officer.share or company not in officer.company_ids:
                raise ValidationError(_(
                    "The Procurement and Inventory Officer must be an active internal user allowed in this company."
                ))
            if not officer.has_group(OFFICER_GROUP):
                raise ValidationError(_(
                    "The configured Procurement and Inventory Officer must have the Procurement and Inventory Officer role."
                ))

    @api.constrains(
        "sedar_default_storage_location_id",
        "sedar_consumption_location_id",
        "sedar_disposal_location_id",
    )
    def _check_sedar_inventory_locations(self):
        expected = (
            ("sedar_default_storage_location_id", "storage"),
            ("sedar_consumption_location_id", "consumption"),
            ("sedar_disposal_location_id", "disposal"),
        )
        for company in self:
            for field_name, role in expected:
                location = company[field_name]
                if location and (
                    location.company_id != company or location.sedar_location_role != role
                ):
                    raise ValidationError(_(
                        "Every configured SEDAR inventory location must belong to the company and have its matching role."
                    ))


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sedar_default_storage_location_id = fields.Many2one(
        related="company_id.sedar_default_storage_location_id", readonly=False
    )
    sedar_consumption_location_id = fields.Many2one(
        related="company_id.sedar_consumption_location_id", readonly=False
    )
    sedar_disposal_location_id = fields.Many2one(
        related="company_id.sedar_disposal_location_id", readonly=False
    )
