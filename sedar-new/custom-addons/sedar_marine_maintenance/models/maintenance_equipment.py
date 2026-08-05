from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    sedar_tugboat_id = fields.Many2one(
        "sedar.tugboat",
        string="Tugboat",
        index=True,
        ondelete="restrict",
    )
    sedar_parent_equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Parent Marine Equipment",
        ondelete="restrict",
    )
    sedar_child_equipment_ids = fields.One2many(
        "maintenance.equipment",
        "sedar_parent_equipment_id",
        string="Sub Equipment",
    )
    sedar_system = fields.Selection(
        [
            ("propulsion", "Propulsion"),
            ("electrical", "Electrical"),
            ("navigation", "Navigation"),
            ("hull", "Hull"),
            ("deck", "Deck Machinery"),
            ("safety", "Safety"),
            ("auxiliary", "Auxiliary"),
            ("other", "Other"),
        ],
        string="Marine System",
        default="other",
    )
    sedar_criticality = fields.Selection(
        [
            ("critical", "Critical"),
            ("major", "Major"),
            ("minor", "Minor"),
        ],
        string="Criticality",
        default="major",
        required=True,
    )
    sedar_installation_date = fields.Date(string="Installation Date")
    sedar_running_interval_hours = fields.Float(
        string="Planned Interval Hours",
        help="Representative PMS interval for the demo. Real intervals require SEDAR confirmation.",
    )
    sedar_last_service_date = fields.Date(string="Last Service Date")
    sedar_last_service_hours = fields.Float(string="Last Service Running Hours")
