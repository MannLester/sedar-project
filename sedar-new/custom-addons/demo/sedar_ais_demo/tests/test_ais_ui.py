from odoo.tests.common import TransactionCase, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestSedarAisInterface(TransactionCase):
    def test_dashboard_uses_progressive_map_layout(self):
        with file_open(
            "sedar_ais_demo/static/src/js/ais_dashboard.js"
        ) as javascript_file:
            javascript = javascript_file.read()
        with file_open(
            "sedar_ais_demo/static/src/xml/ais_dashboard.xml"
        ) as template_file:
            template = template_file.read()

        self.assertIn('detailTab: "overview"', javascript)
        self.assertIn('this.state.selectedId = false', javascript)
        self.assertIn('toggleTug(tugId)', javascript)
        self.assertIn('class="o_sedar_ais_fleet_accordion_button"', template)
        self.assertIn('class="o_sedar_ais_detail_tabs"', template)
        self.assertIn("state.detailTab === 'inventory'", template)
        self.assertIn("state.detailTab === 'equipment'", template)
        self.assertIn("state.detailTab === 'procurement'", template)
