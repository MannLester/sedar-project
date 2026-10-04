/** @odoo-module **/

import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";

const BUNDLE = "/sedar/engine-room/embed.js";

export class SedarEngineRoomAction extends Component {
    static template = "sedar_marine_maintenance.EngineRoomAction";
    static props = ["*"];

    setup() {
        this.host = useRef("host");
        this.unmount = null;
        onMounted(async () => {
            await loadJS(BUNDLE);
            if (this.host.el) {
                this.unmount = window.SedarEngineRoom.mount(this.host.el);
            }
        });
        onWillUnmount(() => this.unmount?.());
    }
}

registry.category("actions").add("sedar_marine_maintenance.engine_room", SedarEngineRoomAction);
