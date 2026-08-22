/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";


export class SedarAisDashboard extends Component {
    static template = "sedar_ais_demo.AisDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            loadError: false,
            advancing: false,
            playing: true,
            fleet: [],
            selectedId: false,
            selectedEquipmentId: false,
            equipmentDetail: false,
            equipmentDetailStatus: "idle",
            equipmentDetailError: false,
            filter: "all",
            generatedAt: false,
            canAdvance: false,
        });
        this.animationTimer = null;
        this.requestGeneration = 0;
        this.onKeydown = (event) => this.handleKeydown(event);
        onWillStart(() => this.loadDashboard());
        onMounted(() => {
            this.startAnimation();
            document.addEventListener("keydown", this.onKeydown);
        });
        onWillUnmount(() => {
            this.stopAnimation();
            this.invalidateEquipmentRequest();
            document.removeEventListener("keydown", this.onKeydown);
        });
    }

    normalizeFleet(fleet = []) {
        return fleet.map((tug) => ({
            ...tug,
            crew: tug.crew || [],
            equipment: tug.equipment || [],
            display_x: tug.previous_x,
            display_y: tug.previous_y,
            target_x: tug.x,
            target_y: tug.y,
        }));
    }

    resetEquipmentDetail() {
        this.state.selectedEquipmentId = false;
        this.state.equipmentDetail = false;
        this.state.equipmentDetailStatus = "idle";
        this.state.equipmentDetailError = false;
    }

    invalidateEquipmentRequest() {
        this.requestGeneration += 1;
        this.resetEquipmentDetail();
        return this.requestGeneration;
    }

    reconcileSelection() {
        const selectedStillExists = this.state.fleet.some((tug) => tug.id === this.state.selectedId);
        if (!selectedStillExists) {
            this.state.selectedId = this.state.fleet[0]?.id || false;
        }
    }

    async loadDashboard() {
        this.invalidateEquipmentRequest();
        this.state.loading = true;
        this.state.loadError = false;
        try {
            const data = await this.orm.call("sedar.ais.position", "get_dashboard_data", []);
            this.state.fleet = this.normalizeFleet(data.fleet);
            this.state.generatedAt = data.generated_at;
            this.state.canAdvance = data.can_advance;
            this.reconcileSelection();
        } catch (error) {
            this.state.loadError = true;
            this.notification.add("Unable to load the simulated AIS feed.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    startAnimation() {
        this.stopAnimation();
        this.animationTimer = setInterval(() => this.animateMarkers(), 900);
    }

    stopAnimation() {
        if (this.animationTimer) {
            clearInterval(this.animationTimer);
            this.animationTimer = null;
        }
    }

    animateMarkers() {
        if (!this.state.playing) {
            return;
        }
        for (const tug of this.state.fleet) {
            if (!["underway", "assisting"].includes(tug.status)) {
                continue;
            }
            const dx = tug.target_x - tug.display_x;
            const dy = tug.target_y - tug.display_y;
            if (Math.abs(dx) + Math.abs(dy) > 0.12) {
                tug.display_x += dx * 0.18;
                tug.display_y += dy * 0.18;
            } else {
                const radians = (tug.course - 90) * Math.PI / 180;
                tug.display_x = Math.max(3, Math.min(97, tug.display_x + Math.cos(radians) * 0.035));
                tug.display_y = Math.max(4, Math.min(96, tug.display_y + Math.sin(radians) * 0.035));
            }
        }
    }

    async advanceSimulation() {
        if (!this.state.canAdvance || this.state.advancing) {
            return;
        }
        this.invalidateEquipmentRequest();
        this.state.advancing = true;
        try {
            const data = await this.orm.call("sedar.ais.position", "action_advance_simulation", []);
            this.state.fleet = this.normalizeFleet(data.fleet);
            this.state.generatedAt = data.generated_at;
            this.reconcileSelection();
            this.notification.add("Simulated AIS reports advanced to the next waypoint.", { type: "success" });
        } catch (error) {
            this.notification.add("Unable to advance the simulated AIS feed.", { type: "danger" });
        } finally {
            this.state.advancing = false;
        }
    }

    togglePlayback() {
        this.state.playing = !this.state.playing;
    }

    selectTug(tugId) {
        if (this.state.selectedId === tugId) {
            return;
        }
        this.invalidateEquipmentRequest();
        this.state.selectedId = tugId;
    }

    closeTugDetail() {
        this.invalidateEquipmentRequest();
        this.state.selectedId = false;
    }

    onTugSelect(event) {
        const value = event.target.value;
        const tugId = value ? Number(value) : false;
        if (tugId) {
            this.selectTug(tugId);
        } else {
            this.closeTugDetail();
        }
    }

    setFilter(filter) {
        this.invalidateEquipmentRequest();
        this.state.filter = filter;
        const visible = this.visibleFleet;
        if (visible.length && !visible.some((tug) => tug.id === this.state.selectedId)) {
            this.state.selectedId = visible[0].id;
        }
    }

    async selectEquipment(equipmentId) {
        const generation = this.invalidateEquipmentRequest();
        this.state.selectedEquipmentId = equipmentId;
        this.state.equipmentDetailStatus = "loading";
        try {
            const detail = await this.orm.call(
                "sedar.ais.position",
                "get_equipment_procurement_detail",
                [equipmentId]
            );
            if (generation !== this.requestGeneration || this.state.selectedEquipmentId !== equipmentId) {
                return;
            }
            this.state.equipmentDetail = detail;
            this.state.equipmentDetailStatus = "ready";
        } catch (error) {
            if (generation !== this.requestGeneration || this.state.selectedEquipmentId !== equipmentId) {
                return;
            }
            this.state.equipmentDetailError = "Procurement detail could not be loaded. Try again.";
            this.state.equipmentDetailStatus = "error";
        }
    }

    closeEquipmentDetail() {
        this.invalidateEquipmentRequest();
    }

    retryEquipmentDetail() {
        if (this.state.selectedEquipmentId) {
            this.selectEquipment(this.state.selectedEquipmentId);
        }
    }

    handleKeydown(event) {
        if (event.key !== "Escape") {
            return;
        }
        if (this.state.selectedEquipmentId) {
            this.closeEquipmentDetail();
        } else if (this.state.selectedId) {
            this.closeTugDetail();
        } else {
            return;
        }
        event.preventDefault();
    }

    get visibleFleet() {
        if (this.state.filter === "all") {
            return this.state.fleet;
        }
        if (this.state.filter === "attention") {
            return this.state.fleet.filter((tug) => ["dry_dock", "maintenance", "offline"].includes(tug.status));
        }
        return this.state.fleet.filter((tug) => tug.status === this.state.filter);
    }

    get selectedTug() {
        return this.state.fleet.find((tug) => tug.id === this.state.selectedId);
    }

    get selectedEquipment() {
        return this.selectedTug?.equipment.find((equipment) => equipment.id === this.state.selectedEquipmentId);
    }

    get activeProcurement() {
        return this.state.equipmentDetail?.active_procurement || [];
    }

    get procurementHistory() {
        return this.state.equipmentDetail?.procurement_history || [];
    }

    get isProcurementLimited() {
        return this.state.equipmentDetail?.access === "limited";
    }

    get summary() {
        const fleet = this.state.fleet;
        return {
            total: fleet.length,
            moving: fleet.filter((tug) => ["underway", "assisting"].includes(tug.status)).length,
            standby: fleet.filter((tug) => ["standby", "berthed"].includes(tug.status)).length,
            attention: fleet.filter((tug) => ["dry_dock", "maintenance", "offline"].includes(tug.status)).length,
        };
    }

    markerStyle(tug) {
        return `left:${tug.display_x}%;top:${tug.display_y}%;--course:${tug.course}deg`;
    }

    markerClass(tug) {
        return `o_sedar_ais_marker o_sedar_ais_marker--${tug.status} ${tug.id === this.state.selectedId ? "is-selected" : ""}`;
    }

    statusClass(status) {
        return `o_sedar_ais_status o_sedar_ais_status--${status}`;
    }

    equipmentStateClass(state) {
        return `o_sedar_ais_equipment_state o_sedar_ais_equipment_state--${state || "unknown"}`;
    }

    formatCoordinate(value, positive, negative) {
        return `${Math.abs(value).toFixed(4)}° ${value >= 0 ? positive : negative}`;
    }

    formatHours(value) {
        return value === false || value === null || value === undefined
            ? "No reading"
            : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })} h`;
    }

    openAttachment(action) {
        this.action.doAction(action);
    }

    openTugboat(tugId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tugboat",
            res_model: "sedar.tugboat",
            res_id: tugId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("sedar_ais_demo.dashboard", SedarAisDashboard);
