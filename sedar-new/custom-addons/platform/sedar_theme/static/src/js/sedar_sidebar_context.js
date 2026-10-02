/** @odoo-module **/

import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

patch(NavBar.prototype, {
    get sedarProcurementNavigation() {
        const procurementRoot = this.menuService
            .getAll()
            .find(
                (menu) =>
                    menu.xmlid === "sedar_purchase_request.menu_sedar_procurement_root"
            );
        return procurementRoot
            ? this.menuService.getMenuAsTree(procurementRoot.id)
            : null;
    },

    get sedarUserName() {
        return user.name || "SEDAR User";
    },

    get sedarUserContext() {
        return this.currentApp?.name || user.activeCompany?.name || "SEDAR ERP";
    },
});
