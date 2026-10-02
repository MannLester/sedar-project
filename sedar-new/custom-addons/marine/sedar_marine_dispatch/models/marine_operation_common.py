from odoo.exceptions import ValidationError


def _validate_operation_tug_links(records):
    for record in records.filtered("operation_tug_id"):
        if record.operation_tug_id.operation_id != record.operation_id:
            raise ValidationError("The operation tug must belong to the selected Marine Operation.")


OPERATION_STATES = [
    ("awaiting_start", "Awaiting Start"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]
