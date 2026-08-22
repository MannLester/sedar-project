from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _inherit = "stock.location"

    sedar_location_role = fields.Selection(
        [
            ("storage", "Storage"),
            ("tug", "Tugboat Stock"),
            ("consumption", "Consumption"),
            ("disposal", "Disposal"),
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

    _sedar_tugboat_unique = models.Constraint(
        "UNIQUE(sedar_tugboat_id)",
        "A tugboat may have only one SEDAR tugboat stock location.",
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
            if role in {"storage", "tug"} and location.usage != "internal":
                raise ValidationError(_("Storage and tugboat stock locations must be internal locations."))
            if role in {"consumption", "disposal"} and location.usage != "inventory":
                raise ValidationError(_("Consumption and disposal locations must be inventory-loss locations."))
            if role == "tug" and not location.sedar_tugboat_id:
                raise ValidationError(_("A Tugboat Stock location must identify its tugboat."))
            if role != "tug" and location.sedar_tugboat_id:
                raise ValidationError(_("Only Tugboat Stock locations may identify a tugboat."))
            tug_company = getattr(location.sedar_tugboat_id, "company_id", False)
            if tug_company and tug_company != location.company_id:
                raise ValidationError(_("A tugboat stock location must belong to its tugboat's company."))
