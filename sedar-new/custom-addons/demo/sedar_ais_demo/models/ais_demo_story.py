from datetime import datetime

from odoo import models


MODULE = "sedar_ais_demo"


def _record(env, model, xmlid, values, update=True):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid),
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            if update:
                record.sudo().write(values)
            return record, False
        data.unlink()
    record = env[model].sudo().create(values)
    env["ir.model.data"].sudo().create({
        "module": MODULE,
        "name": xmlid,
        "model": model,
        "res_id": record.id,
        "noupdate": True,
    })
    return record, True


class ResCompany(models.Model):
    _inherit = "res.company"

    def _sedar_ensure_ais_demo_story(self):
        self.ensure_one()
        env = self.env
        atlas = env.ref(
            "sedar_service_order_demo.tug_atlas", raise_if_not_found=False
        )
        equipment = env.ref(
            "sedar_ais_demo.dashboard_atlas_main_engine",
            raise_if_not_found=False,
        )
        maintenance_equipment = env.ref(
            "sedar_marine_maintenance.atlas_main_engine",
            raise_if_not_found=False,
        )
        officer = env.ref(
            "sedar_purchase_request.user_procurement_manager",
            raise_if_not_found=False,
        ) or env.ref("sedar_ais_demo.user_ais_demo", raise_if_not_found=False)
        if not atlas or not officer or not atlas.stock_location_id:
            return False
        if not equipment and maintenance_equipment:
            env["ir.model.data"].sudo().create({
                "module": MODULE,
                "name": "dashboard_atlas_main_engine",
                "model": maintenance_equipment._name,
                "res_id": maintenance_equipment.id,
                "noupdate": True,
            })
            equipment = maintenance_equipment
        elif not equipment:
            equipment, _created = _record(
                env,
                "maintenance.equipment",
                "dashboard_atlas_main_engine",
                {
                    "name": "STS Atlas Dashboard Main Engine",
                    "company_id": self.id,
                    "sedar_tugboat_id": atlas.id,
                    "sedar_system": "propulsion",
                    "sedar_criticality": "critical",
                },
            )
        product, product_created = _record(
            env,
            "product.product",
            "dashboard_atlas_impeller",
            {
                "name": "Demo Main Engine Cooling Pump Impeller",
                "type": "consu",
                "is_storable": True,
                "uom_id": env.ref("uom.product_uom_unit").id,
                "default_code": "DEMO-ATLAS-IMP-001",
                "sedar_inventory_item": True,
                "sedar_item_type": "spare_part",
                "sedar_readiness_critical": True,
                "sedar_compatibility_scope": "restricted",
                "sedar_compatible_tugboat_ids": [(6, 0, [atlas.id])],
                "sedar_reorder_point": 4,
            },
        )
        if product_created:
            env["stock.quant"]._update_available_quantity(
                product, atlas.stock_location_id, 1
            )
        _record(
            env,
            "sedar.tug.stock.requirement",
            "dashboard_atlas_impeller_requirement",
            {
                "company_id": self.id,
                "product_id": product.id,
                "tugboat_id": atlas.id,
                "required_qty": 4,
                "active": True,
                "note": "Fleet dashboard demonstration shortage.",
            },
        )
        env["sedar.replenishment.demand"]._sync_inventory_shortages()
        active_request, _created = _record(
            env,
            "sedar.purchase.request",
            "dashboard_atlas_active_request",
            {
                "requester_id": officer.id,
                "company_id": self.id,
                "currency_id": self.currency_id.id,
                "source_type": "maintenance",
                "equipment_id": equipment.id,
                "required_date": datetime(2026, 10, 15, 8),
                "priority": "urgent",
                "justification": (
                    "Restore the STS Atlas main-engine cooling pump spare reserve."
                ),
                "state": "draft",
            },
            update=False,
        )
        active_line, _created = _record(
            env,
            "sedar.purchase.request.line",
            "dashboard_atlas_active_request_line",
            {
                "request_id": active_request.id,
                "product_id": product.id,
                "quantity": 3,
                "estimated_unit_price": 18500,
                "source_location_id": atlas.stock_location_id.id,
                "need_reason": "Three units are needed to restore the onboard minimum.",
            },
            update=False,
        )
        if active_request.state == "draft":
            active_request.sudo().write({
                "state": "approved",
                "approved_by_id": officer.id,
                "approved_at": datetime(2026, 10, 4, 9),
            })
        self._sedar_ensure_ais_demo_bids(active_request, active_line, officer)
        history_request, _created = _record(
            env,
            "sedar.purchase.request",
            "dashboard_atlas_history_request",
            {
                "requester_id": officer.id,
                "company_id": self.id,
                "currency_id": self.currency_id.id,
                "source_type": "maintenance",
                "equipment_id": equipment.id,
                "required_date": datetime(2026, 9, 20, 8),
                "priority": "normal",
                "justification": "Earlier cooling-pump gasket sourcing exercise.",
                "state": "draft",
            },
            update=False,
        )
        _record(
            env,
            "sedar.purchase.request.line",
            "dashboard_atlas_history_request_line",
            {
                "request_id": history_request.id,
                "product_id": product.id,
                "quantity": 1,
                "estimated_unit_price": 3200,
                "source_location_id": atlas.stock_location_id.id,
                "need_reason": "Superseded after engineering inspection.",
            },
            update=False,
        )
        if history_request.state == "draft":
            history_request.sudo().write({"state": "cancelled"})
        return True

    def _sedar_ensure_ais_demo_bids(self, request, request_line, officer):
        for index, (name, price, delivery_date) in enumerate([
            ("Demo Batangas Marine Supply", 17950, "2026-10-11"),
            ("Demo Bay Industrial Parts", 18600, "2026-10-09"),
        ], start=1):
            bidder, _created = _record(
                self.env,
                "res.partner",
                f"dashboard_bidder_{index}",
                {
                    "name": name,
                    "is_company": True,
                    "supplier_rank": 1,
                    "company_id": self.id,
                },
            )
            bid, _created = _record(
                self.env,
                "sedar.purchase.bid",
                f"dashboard_atlas_bid_{index}",
                {
                    "request_id": request.id,
                    "bidder_id": bidder.id,
                    "state": "received",
                    "capture_source": "manual",
                    "received_by_id": officer.id,
                    "received_at": datetime(2026, 10, 4, 10 + index),
                    "received_date": "2026-10-04",
                    "validity_date": "2026-10-20",
                    "promised_delivery_date": delivery_date,
                    "delivery_terms": "Delivered to SEDAR Batangas base.",
                    "payment_terms": "30 days after delivery and acceptance.",
                    "warranty_notes": "Twelve-month manufacturer warranty.",
                },
                update=False,
            )
            _record(
                self.env,
                "sedar.purchase.bid.line",
                f"dashboard_atlas_bid_line_{index}",
                {
                    "bid_id": bid.id,
                    "request_line_id": request_line.id,
                    "quantity": request_line.quantity,
                    "unit_price": price,
                    "promised_delivery_date": delivery_date,
                    "delivery_terms": "Packed and delivered to the main warehouse.",
                },
                update=False,
            )
