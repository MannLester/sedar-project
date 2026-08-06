/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
patch(WebClient.prototype, {
    async _subscribePush() {
        // Browser push is intentionally disabled for the current desktop-first MVP.
    },
});
