from odoo.exceptions import AccessError


SEVERITIES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


def _check_hsse_manager(recordset):
    if recordset.env.su:
        return
    if not recordset.env.user.has_group("sedar_hsse.group_sedar_hsse_manager"):
        raise AccessError("Only an HSSE Manager may perform this action.")
