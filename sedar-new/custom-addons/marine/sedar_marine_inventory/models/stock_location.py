from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _inherit = "stock.location"

    sedar_location_role = fields.Selection(
        [
            ("storage", "Storage"),
            ("storage_quarantine", "Storage Quarantine"),
            ("tug", "Tugboat Stock"),
            ("tug_quarantine", "Tugboat Quarantine"),
            ("consumption", "Consumption"),
            ("disposal", "Disposal"),
            ("adjustment", "Inventory Adjustment"),
        ],
        string="SEDAR Inventory Role",
        index=True,
        copy=False,
    )
    sedar_tugboat_id = fields.Many2one(
        "sedar.tugboat",
        string="SEDAR Tugboat",
        index=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )

    _sedar_tugboat_role_unique = models.Constraint(
        "UNIQUE(sedar_tugboat_id, sedar_location_role)",
        "A tugboat may have only one SEDAR location for each inventory role.",
    )

    @api.constrains("sedar_location_role", "sedar_tugboat_id", "usage", "company_id")
    def _check_sedar_location_contract(self):
        for location in self:
            role = location.sedar_location_role
            if not role:
                if location.sedar_tugboat_id:
                    raise ValidationError(_("A tugboat link requires the Tugboat Stock role."))
                continue
            if not location.company_id:
                raise ValidationError(_("A SEDAR inventory location must belong to a company."))
            if role in {"storage", "storage_quarantine", "tug", "tug_quarantine"} and location.usage != "internal":
                raise ValidationError(_("Storage, quarantine, and tugboat stock locations must be internal locations."))
            if role in {"consumption", "disposal", "adjustment"} and location.usage != "inventory":
                raise ValidationError(_("Consumption and disposal locations must be inventory-loss locations."))
            if role in {"tug", "tug_quarantine"} and not location.sedar_tugboat_id:
                raise ValidationError(_("A tugboat inventory location must identify its tugboat."))
            if role not in {"tug", "tug_quarantine"} and location.sedar_tugboat_id:
                raise ValidationError(_("Only tugboat inventory locations may identify a tugboat."))
            tug_company = getattr(location.sedar_tugboat_id, "company_id", False)
            if tug_company and tug_company != location.company_id:
                raise ValidationError(_("A tugboat stock location must belong to its tugboat's company."))
            if role == "tug_quarantine" and (
                not location.location_id
                or location.location_id.sedar_location_role != "tug"
                or location.location_id.sedar_tugboat_id != location.sedar_tugboat_id
            ):
                raise ValidationError(_("A tugboat quarantine location must be inside that tugboat's serviceable location."))
            if role == "storage_quarantine" and (
                not location.location_id
                or location.location_id.sedar_location_role != "storage"
            ):
                raise ValidationError(_("A storage quarantine location must be inside a tagged Storage location."))
