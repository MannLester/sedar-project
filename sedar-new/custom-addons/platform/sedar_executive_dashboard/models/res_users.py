from odoo import fields, models


EXECUTIVE_DASHBOARD_VIEWS = [
    ("owner", "Owner Overview"),
    ("operations", "Operations"),
    ("finance", "Finance"),
    ("people", "Crewing & Safety"),
]


class ResUsers(models.Model):
    _inherit = "res.users"

    sedar_executive_dashboard_view = fields.Selection(
        EXECUTIVE_DASHBOARD_VIEWS,
        string="Preferred Executive Dashboard View",
        default="owner",
        required=True,
    )

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["sedar_executive_dashboard_view"]

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["sedar_executive_dashboard_view"]
