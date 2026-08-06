/** @odoo-module **/

import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

patch(NavBar.prototype, {
    get sedarUserName() {
        return user.name || "SEDAR User";
    },

    get sedarUserContext() {
        return this.currentApp?.name || user.activeCompany?.name || "SEDAR ERP";
    },
});
