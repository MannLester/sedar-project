# SEDAR ERP MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Odoo 17.0 Community prototype covering all 9 SEDAR Tug Services departments (Finance, Tug Operations, Technical/Maintenance, HSSE, Crewing, Procurement, Inventory, HR, Document Control) plus a KPI dashboard, per `docs/superpowers/specs/2026-07-05-sedar-erp-mvp-design.md`.

**Architecture:** Docker Compose runs Odoo 17.0 Community + PostgreSQL 15. Native Community apps (Invoicing, Purchase, Inventory, Maintenance, Employees, Recruitment) are installed and lightly configured. Five custom addons (`sedar_base`, `sedar_tug_ops`, `sedar_hsse`, `sedar_crewing`, `sedar_doccontrol`, `sedar_dashboard`) are built from scratch to cover what Community doesn't provide.

**Tech Stack:** Odoo 17.0 (Python 3.10 ORM, XML views), PostgreSQL 15, Docker Compose.

## Global Constraints

- Odoo Community Edition only — no Enterprise modules/features (per spec's "Constraints" section).
- Every custom model uses the `sedar.` name prefix and lives under `addons/sedar_*`.
- Every module with fields that have a natural expiry date (permits, certifications, medical certs, vessel certs, insurance, doc records) inherits `sedar.expiry.mixin` from `sedar_base` — do not re-implement expiry logic per spec's "shared expiry-alert logic" requirement.
- Demo data must be Philippine tugboat-industry realistic (PHP currency, MARINA/PCG/PPA-style permits, named vessels, local ports) per spec.
- Each module gets `ir.model.access.csv` granting `base.group_user` full CRUD (perm_read/write/create/unlink = 1,1,1,1) — no fine-grained roles for MVP (client hasn't specified roles yet).
- Commit after every task.

---

### Task 1: Docker Compose + Odoo/Postgres infrastructure scaffold

**Files:**
- Create: `docker-compose.yml`
- Create: `config/odoo.conf`
- Create: `.gitignore`

**Interfaces:**
- Produces: a running Odoo instance at `localhost:8069`, addons path `/mnt/extra-addons` mapped to `./addons` on the host — every later task's module lives under `./addons/<module_name>` and becomes installable once the container is running.

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
version: "3.8"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
    volumes:
      - db-data:/var/lib/postgresql/data
  odoo:
    image: odoo:17.0
    depends_on:
      - db
    ports:
      - "8069:8069"
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    volumes:
      - ./addons:/mnt/extra-addons
      - odoo-data:/var/lib/odoo
      - ./config/odoo.conf:/etc/odoo/odoo.conf
volumes:
  db-data:
  odoo-data:
```

- [ ] **Step 2: Create `config/odoo.conf`**

```ini
[options]
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
db_host = db
db_user = odoo
db_password = odoo
```

- [ ] **Step 3: Create `.gitignore`**

```
*.pyc
__pycache__/
.vscode/
```

- [ ] **Step 4: Start the stack and create the `sedar` database**

Run: `docker compose up -d`
Run: `docker compose exec odoo odoo -d sedar --stop-after-init --without-demo=all`
Expected: command exits 0, no traceback in `docker compose logs odoo`.

- [ ] **Step 5: Verify the instance boots and is reachable**

Run: `curl -sI http://localhost:8069/web/login`
Expected: `HTTP/1.1 200 OK`

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml config/.gitignore config/odoo.conf .gitignore
git commit -m "infra: add Odoo 17 + Postgres docker-compose scaffold"
```

---

### Task 2: `sedar_base` module — shared expiry mixin

**Files:**
- Create: `addons/sedar_base/__init__.py`
- Create: `addons/sedar_base/__manifest__.py`
- Create: `addons/sedar_base/models/__init__.py`
- Create: `addons/sedar_base/models/expiry_mixin.py`
- Test: `addons/sedar_base/tests/__init__.py`
- Test: `addons/sedar_base/tests/test_expiry_mixin.py`

**Interfaces:**
- Produces: abstract model `sedar.expiry.mixin` with fields `expiry_date` (Date) and computed/stored `expiry_status` (Selection: `ok`/`warning`/`expired`). Any later model does `_inherit = ['sedar.expiry.mixin']` to get both fields automatically.

- [ ] **Step 1: Create module skeleton**

`addons/sedar_base/__init__.py`:
```python
from . import models
```

`addons/sedar_base/__manifest__.py`:
```python
{
    'name': 'SEDAR Base',
    'version': '17.0.1.0.0',
    'summary': 'Shared base utilities for SEDAR custom modules',
    'category': 'Tools',
    'depends': ['base'],
    'data': [],
    'installable': True,
    'application': False,
}
```

`addons/sedar_base/models/__init__.py`:
```python
from . import expiry_mixin
```

- [ ] **Step 2: Write the expiry mixin**

`addons/sedar_base/models/expiry_mixin.py`:
```python
from odoo import models, fields, api


class SedarExpiryMixin(models.AbstractModel):
    _name = 'sedar.expiry.mixin'
    _description = 'Shared expiry-date tracking'

    expiry_date = fields.Date(string='Expiry Date')
    expiry_status = fields.Selection(
        [('ok', 'Valid'), ('warning', 'Expiring Soon'), ('expired', 'Expired')],
        string='Status', compute='_compute_expiry_status', store=True,
    )

    @api.depends('expiry_date')
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.expiry_date:
                rec.expiry_status = 'ok'
            elif rec.expiry_date < today:
                rec.expiry_status = 'expired'
            elif (rec.expiry_date - today).days <= 30:
                rec.expiry_status = 'warning'
            else:
                rec.expiry_status = 'ok'
```

- [ ] **Step 3: Write the failing test**

`addons/sedar_base/tests/__init__.py`:
```python
from . import test_expiry_mixin
```

`addons/sedar_base/tests/test_expiry_mixin.py`:
```python
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.fields import Date


class TestExpiryMixin(TransactionCase):

    def _make_concrete_model_record(self, expiry_date):
        # sedar.hsse.permit inherits the mixin; used here once it exists (Task 9).
        # Until then, this test exercises the mixin via a minimal throwaway model
        # is not possible in Odoo without a real table, so this test is written
        # against sedar.hsse.permit and only runs once Task 9 installs it.
        return self.env['sedar.hsse.permit'].create({
            'name': 'Test Permit',
            'expiry_date': expiry_date,
        })

    def test_expired_status(self):
        rec = self._make_concrete_model_record(Date.today() - timedelta(days=1))
        self.assertEqual(rec.expiry_status, 'expired')

    def test_warning_status(self):
        rec = self._make_concrete_model_record(Date.today() + timedelta(days=10))
        self.assertEqual(rec.expiry_status, 'warning')

    def test_ok_status(self):
        rec = self._make_concrete_model_record(Date.today() + timedelta(days=365))
        self.assertEqual(rec.expiry_status, 'ok')
```

> Note: this test depends on `sedar.hsse.permit` (built in Task 9). Leave it written now per TDD intent, but skip running it until Task 9 installs that model — running it here against a not-yet-existing model will fail with "model not found", which is expected at this point. Task 9's steps re-run this exact test as its own verification.

- [ ] **Step 4: Commit**

```bash
git add addons/sedar_base
git commit -m "feat(sedar_base): add shared expiry-tracking mixin"
```

---

### Task 3: `sedar_tug_ops` — Vessel model

**Files:**
- Create: `addons/sedar_tug_ops/__init__.py`
- Create: `addons/sedar_tug_ops/__manifest__.py`
- Create: `addons/sedar_tug_ops/models/__init__.py`
- Create: `addons/sedar_tug_ops/models/vessel.py`
- Create: `addons/sedar_tug_ops/views/vessel_views.xml`
- Create: `addons/sedar_tug_ops/views/menu.xml`
- Create: `addons/sedar_tug_ops/security/ir.model.access.csv`
- Test: `addons/sedar_tug_ops/tests/__init__.py`
- Test: `addons/sedar_tug_ops/tests/test_vessel.py`

**Interfaces:**
- Produces: model `sedar.vessel` with fields `name` (Char), `registry_no` (Char), `vessel_type` (Selection: `tug`/`barge`), `capacity` (Float), `status` (Selection: `active`/`dry_dock`/`standby`). Root menu "Tug Operations" (`sedar_tug_ops.menu_root`) — later tasks in this module add sub-menus under it.
- Consumes: nothing yet (first model in this module).

- [ ] **Step 1: Create module skeleton**

`addons/sedar_tug_ops/__init__.py`:
```python
from . import models
```

`addons/sedar_tug_ops/__manifest__.py`:
```python
{
    'name': 'SEDAR Tug Operations',
    'version': '17.0.1.0.0',
    'summary': 'Job dispatch, scheduling, voyage logs, fuel, towage billing',
    'category': 'Operations',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/vessel_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
```

`addons/sedar_tug_ops/models/__init__.py`:
```python
from . import vessel
```

- [ ] **Step 2: Write the Vessel model**

`addons/sedar_tug_ops/models/vessel.py`:
```python
from odoo import models, fields


class SedarVessel(models.Model):
    _name = 'sedar.vessel'
    _description = 'Tugboat / Barge Vessel'
    _order = 'name'

    name = fields.Char(required=True)
    registry_no = fields.Char(string='IMO/Registry No.')
    vessel_type = fields.Selection(
        [('tug', 'Tug'), ('barge', 'Barge')], required=True, default='tug')
    capacity = fields.Float(string='Capacity (BHP/DWT)')
    status = fields.Selection(
        [('active', 'Active'), ('dry_dock', 'Dry Dock'), ('standby', 'Standby')],
        default='active', required=True)
```

- [ ] **Step 3: Write security access**

`addons/sedar_tug_ops/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sedar_vessel_user,sedar.vessel.user,model_sedar_vessel,base.group_user,1,1,1,1
```

- [ ] **Step 4: Write views and menu**

`addons/sedar_tug_ops/views/vessel_views.xml`:
```xml
<odoo>
    <record id="view_sedar_vessel_list" model="ir.ui.view">
        <field name="name">sedar.vessel.list</field>
        <field name="model">sedar.vessel</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="registry_no"/>
                <field name="vessel_type"/>
                <field name="status"/>
            </list>
        </field>
    </record>

    <record id="view_sedar_vessel_form" model="ir.ui.view">
        <field name="name">sedar.vessel.form</field>
        <field name="model">sedar.vessel</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="registry_no"/>
                        <field name="vessel_type"/>
                        <field name="capacity"/>
                        <field name="status"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_sedar_vessel" model="ir.actions.act_window">
        <field name="name">Vessels</field>
        <field name="res_model">sedar.vessel</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

`addons/sedar_tug_ops/views/menu.xml`:
```xml
<odoo>
    <menuitem id="menu_root" name="Tug Operations" sequence="10"/>
    <menuitem id="menu_vessel" name="Vessels" parent="menu_root"
              action="action_sedar_vessel" sequence="10"/>
</odoo>
```

- [ ] **Step 5: Write the failing test**

`addons/sedar_tug_ops/tests/__init__.py`:
```python
from . import test_vessel
```

`addons/sedar_tug_ops/tests/test_vessel.py`:
```python
from odoo.tests.common import TransactionCase


class TestVessel(TransactionCase):

    def test_create_vessel(self):
        vessel = self.env['sedar.vessel'].create({
            'name': 'SEDAR Kalinga',
            'registry_no': 'IMO-9123456',
            'vessel_type': 'tug',
            'capacity': 3200.0,
        })
        self.assertEqual(vessel.status, 'active')
        self.assertEqual(vessel.vessel_type, 'tug')
```

- [ ] **Step 6: Install the module and run the test**

Run: `docker compose exec odoo odoo -d sedar -i sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: log shows `1 tests ... in ... OK` (or equivalent "0 failed"), no traceback.

- [ ] **Step 7: Commit**

```bash
git add addons/sedar_tug_ops
git commit -m "feat(sedar_tug_ops): add Vessel model, views, menu"
```

---

### Task 4: `sedar_tug_ops` — Job Order (dispatch) model

**Files:**
- Modify: `addons/sedar_tug_ops/models/__init__.py`
- Create: `addons/sedar_tug_ops/models/job_order.py`
- Create: `addons/sedar_tug_ops/data/ir_sequence_data.xml`
- Create: `addons/sedar_tug_ops/views/job_order_views.xml`
- Modify: `addons/sedar_tug_ops/views/menu.xml`
- Modify: `addons/sedar_tug_ops/security/ir.model.access.csv`
- Modify: `addons/sedar_tug_ops/__manifest__.py`
- Test: `addons/sedar_tug_ops/tests/test_job_order.py`
- Modify: `addons/sedar_tug_ops/tests/__init__.py`

**Interfaces:**
- Consumes: `sedar.vessel` (Task 3).
- Produces: model `sedar.job.order` with fields `name` (auto-sequence), `customer_id` (Many2one `res.partner`), `vessel_id` (Many2one `sedar.vessel`), `origin_port`/`destination_port` (Char), `requested_date` (Datetime), `state` (Selection: `requested`/`dispatched`/`in_progress`/`completed`/`billed`), and action methods `action_dispatch()`, `action_start()`, `action_complete()`. Later tasks (Voyage Log, Towage Billing) reference `sedar.job.order` by this exact model name and use `state` values verbatim.

- [ ] **Step 1: Write the failing test**

`addons/sedar_tug_ops/tests/test_job_order.py`:
```python
from odoo.tests.common import TransactionCase


class TestJobOrder(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Bantay'})
        self.customer = self.env['res.partner'].create({'name': 'Manila Port Authority'})

    def test_create_and_dispatch(self):
        job = self.env['sedar.job.order'].create({
            'customer_id': self.customer.id,
            'vessel_id': self.vessel.id,
            'origin_port': 'Manila South Harbor',
            'destination_port': 'Batangas Port',
        })
        self.assertEqual(job.state, 'requested')
        self.assertNotEqual(job.name, 'New')
        job.action_dispatch()
        self.assertEqual(job.state, 'dispatched')
        job.action_start()
        self.assertEqual(job.state, 'in_progress')
        job.action_complete()
        self.assertEqual(job.state, 'completed')
```

Add to `addons/sedar_tug_ops/tests/__init__.py`:
```python
from . import test_vessel
from . import test_job_order
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -u sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: FAIL — `sedar.job.order` model does not exist yet.

- [ ] **Step 3: Write the Job Order model**

`addons/sedar_tug_ops/models/job_order.py`:
```python
from odoo import models, fields, api


class SedarJobOrder(models.Model):
    _name = 'sedar.job.order'
    _description = 'Tug Job Order / Dispatch'
    _order = 'requested_date desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True)
    origin_port = fields.Char()
    destination_port = fields.Char()
    requested_date = fields.Datetime(required=True, default=fields.Datetime.now)
    state = fields.Selection([
        ('requested', 'Requested'),
        ('dispatched', 'Dispatched'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('billed', 'Billed'),
    ], default='requested', string='Status', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sedar.job.order') or 'New'
        return super().create(vals_list)

    def action_dispatch(self):
        self.write({'state': 'dispatched'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed'})
```

Update `addons/sedar_tug_ops/models/__init__.py`:
```python
from . import vessel
from . import job_order
```

- [ ] **Step 4: Add the sequence**

`addons/sedar_tug_ops/data/ir_sequence_data.xml`:
```xml
<odoo>
    <record id="seq_sedar_job_order" model="ir.sequence">
        <field name="name">SEDAR Job Order</field>
        <field name="code">sedar.job.order</field>
        <field name="prefix">JO/%(year)s/</field>
        <field name="padding">4</field>
    </record>
</odoo>
```

- [ ] **Step 5: Add views and menu**

`addons/sedar_tug_ops/views/job_order_views.xml`:
```xml
<odoo>
    <record id="view_sedar_job_order_list" model="ir.ui.view">
        <field name="name">sedar.job.order.list</field>
        <field name="model">sedar.job.order</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="customer_id"/>
                <field name="vessel_id"/>
                <field name="requested_date"/>
                <field name="state"/>
            </list>
        </field>
    </record>

    <record id="view_sedar_job_order_form" model="ir.ui.view">
        <field name="name">sedar.job.order.form</field>
        <field name="model">sedar.job.order</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_dispatch" string="Dispatch" type="object"
                            invisible="state != 'requested'"/>
                    <button name="action_start" string="Start" type="object"
                            invisible="state != 'dispatched'"/>
                    <button name="action_complete" string="Complete" type="object"
                            invisible="state != 'in_progress'"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="customer_id"/>
                        <field name="vessel_id"/>
                        <field name="origin_port"/>
                        <field name="destination_port"/>
                        <field name="requested_date"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_sedar_job_order" model="ir.actions.act_window">
        <field name="name">Job Orders / Dispatch</field>
        <field name="res_model">sedar.job.order</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_tug_ops/views/menu.xml`:
```xml
<menuitem id="menu_job_order" name="Job Orders" parent="menu_root"
          action="action_sedar_job_order" sequence="20"/>
```

- [ ] **Step 6: Add security row**

Append to `addons/sedar_tug_ops/security/ir.model.access.csv`:
```csv
access_sedar_job_order_user,sedar.job.order.user,model_sedar_job_order,base.group_user,1,1,1,1
```

- [ ] **Step 7: Register new data files in manifest**

Update `addons/sedar_tug_ops/__manifest__.py` `data` list:
```python
'data': [
    'security/ir.model.access.csv',
    'data/ir_sequence_data.xml',
    'views/vessel_views.xml',
    'views/job_order_views.xml',
    'views/menu.xml',
],
```

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: PASS, 0 failures.

- [ ] **Step 9: Commit**

```bash
git add addons/sedar_tug_ops
git commit -m "feat(sedar_tug_ops): add Job Order dispatch workflow"
```

---

### Task 5: `sedar_tug_ops` — Voyage Log + Fuel Monitoring

**Files:**
- Modify: `addons/sedar_tug_ops/models/__init__.py`
- Create: `addons/sedar_tug_ops/models/voyage_log.py`
- Create: `addons/sedar_tug_ops/models/fuel_log.py`
- Create: `addons/sedar_tug_ops/views/voyage_fuel_views.xml`
- Modify: `addons/sedar_tug_ops/views/menu.xml`
- Modify: `addons/sedar_tug_ops/security/ir.model.access.csv`
- Modify: `addons/sedar_tug_ops/__manifest__.py`
- Test: `addons/sedar_tug_ops/tests/test_voyage_fuel.py`
- Modify: `addons/sedar_tug_ops/tests/__init__.py`

**Interfaces:**
- Consumes: `sedar.job.order` (Task 4), `sedar.vessel` (Task 3).
- Produces: models `sedar.voyage.log` (fields `job_order_id`, `departure_time`, `arrival_time`, `distance_nm`, `weather_notes`) and `sedar.fuel.log` (fields `vessel_id`, `date`, `liters`, `cost`, `currency_id`).

- [ ] **Step 1: Write the failing test**

`addons/sedar_tug_ops/tests/test_voyage_fuel.py`:
```python
from odoo.tests.common import TransactionCase


class TestVoyageFuel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Tagumpay'})
        self.customer = self.env['res.partner'].create({'name': 'Batangas Terminal Inc.'})
        self.job = self.env['sedar.job.order'].create({
            'customer_id': self.customer.id,
            'vessel_id': self.vessel.id,
        })

    def test_voyage_log(self):
        log = self.env['sedar.voyage.log'].create({
            'job_order_id': self.job.id,
            'distance_nm': 42.5,
            'weather_notes': 'Calm seas, 2ft swell',
        })
        self.assertEqual(log.job_order_id, self.job)

    def test_fuel_log(self):
        fuel = self.env['sedar.fuel.log'].create({
            'vessel_id': self.vessel.id,
            'liters': 850.0,
            'cost': 62000.0,
        })
        self.assertEqual(fuel.vessel_id, self.vessel)
        self.assertEqual(fuel.liters, 850.0)
```

Add to `addons/sedar_tug_ops/tests/__init__.py`:
```python
from . import test_voyage_fuel
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -u sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: FAIL — models don't exist yet.

- [ ] **Step 3: Write the models**

`addons/sedar_tug_ops/models/voyage_log.py`:
```python
from odoo import models, fields


class SedarVoyageLog(models.Model):
    _name = 'sedar.voyage.log'
    _description = 'Voyage Log'
    _order = 'departure_time desc'

    job_order_id = fields.Many2one('sedar.job.order', required=True, ondelete='cascade')
    departure_time = fields.Datetime()
    arrival_time = fields.Datetime()
    distance_nm = fields.Float(string='Distance (NM)')
    weather_notes = fields.Text()
```

`addons/sedar_tug_ops/models/fuel_log.py`:
```python
from odoo import models, fields


class SedarFuelLog(models.Model):
    _name = 'sedar.fuel.log'
    _description = 'Fuel Monitoring'
    _order = 'date desc'

    vessel_id = fields.Many2one('sedar.vessel', required=True)
    date = fields.Date(default=fields.Date.context_today)
    liters = fields.Float(string='Liters Consumed')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    cost = fields.Monetary(currency_field='currency_id')
```

Update `addons/sedar_tug_ops/models/__init__.py`:
```python
from . import vessel
from . import job_order
from . import voyage_log
from . import fuel_log
```

- [ ] **Step 4: Add views and menu**

`addons/sedar_tug_ops/views/voyage_fuel_views.xml`:
```xml
<odoo>
    <record id="view_sedar_voyage_log_list" model="ir.ui.view">
        <field name="name">sedar.voyage.log.list</field>
        <field name="model">sedar.voyage.log</field>
        <field name="arch" type="xml">
            <list>
                <field name="job_order_id"/>
                <field name="departure_time"/>
                <field name="arrival_time"/>
                <field name="distance_nm"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_voyage_log_form" model="ir.ui.view">
        <field name="name">sedar.voyage.log.form</field>
        <field name="model">sedar.voyage.log</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="job_order_id"/>
                        <field name="departure_time"/>
                        <field name="arrival_time"/>
                        <field name="distance_nm"/>
                        <field name="weather_notes"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_voyage_log" model="ir.actions.act_window">
        <field name="name">Voyage Log</field>
        <field name="res_model">sedar.voyage.log</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_fuel_log_list" model="ir.ui.view">
        <field name="name">sedar.fuel.log.list</field>
        <field name="model">sedar.fuel.log</field>
        <field name="arch" type="xml">
            <list>
                <field name="vessel_id"/>
                <field name="date"/>
                <field name="liters"/>
                <field name="cost"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_fuel_log_form" model="ir.ui.view">
        <field name="name">sedar.fuel.log.form</field>
        <field name="model">sedar.fuel.log</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="vessel_id"/>
                        <field name="date"/>
                        <field name="liters"/>
                        <field name="cost"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_fuel_log" model="ir.actions.act_window">
        <field name="name">Fuel Monitoring</field>
        <field name="res_model">sedar.fuel.log</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_tug_ops/views/menu.xml`:
```xml
<menuitem id="menu_voyage_log" name="Voyage Log" parent="menu_root"
          action="action_sedar_voyage_log" sequence="30"/>
<menuitem id="menu_fuel_log" name="Fuel Monitoring" parent="menu_root"
          action="action_sedar_fuel_log" sequence="40"/>
```

- [ ] **Step 5: Add security rows**

Append to `addons/sedar_tug_ops/security/ir.model.access.csv`:
```csv
access_sedar_voyage_log_user,sedar.voyage.log.user,model_sedar_voyage_log,base.group_user,1,1,1,1
access_sedar_fuel_log_user,sedar.fuel.log.user,model_sedar_fuel_log,base.group_user,1,1,1,1
```

- [ ] **Step 6: Register view file in manifest**

Add `'views/voyage_fuel_views.xml'` to the `data` list in `addons/sedar_tug_ops/__manifest__.py` (before `views/menu.xml`).

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_tug_ops
git commit -m "feat(sedar_tug_ops): add Voyage Log and Fuel Monitoring"
```

---

### Task 6: `sedar_tug_ops` — Towage Billing + invoice creation

**Files:**
- Modify: `addons/sedar_tug_ops/models/__init__.py`
- Create: `addons/sedar_tug_ops/models/towage_billing.py`
- Create: `addons/sedar_tug_ops/views/towage_billing_views.xml`
- Modify: `addons/sedar_tug_ops/views/menu.xml`
- Modify: `addons/sedar_tug_ops/security/ir.model.access.csv`
- Modify: `addons/sedar_tug_ops/__manifest__.py`
- Test: `addons/sedar_tug_ops/tests/test_towage_billing.py`
- Modify: `addons/sedar_tug_ops/tests/__init__.py`

**Interfaces:**
- Consumes: `sedar.job.order` (Task 4), Odoo's native `account.move` (Invoicing app, installed in Task 15 — but the model exists in Odoo core's `account` module which is already a manifest dependency, so it is available now).
- Produces: model `sedar.towage.billing` with fields `job_order_id`, `rate_basis` (`hour`/`job`), `rate`, `hours`, computed `amount`, `invoice_id`, and method `action_create_invoice()` which creates an `account.move` and flips the linked job order to `state = 'billed'`.

- [ ] **Step 1: Write the failing test**

`addons/sedar_tug_ops/tests/test_towage_billing.py`:
```python
from odoo.tests.common import TransactionCase


class TestTowageBilling(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Matatag'})
        self.customer = self.env['res.partner'].create({'name': 'Subic Bay Freeport'})
        self.job = self.env['sedar.job.order'].create({
            'customer_id': self.customer.id,
            'vessel_id': self.vessel.id,
        })

    def test_amount_computation_per_job(self):
        bill = self.env['sedar.towage.billing'].create({
            'job_order_id': self.job.id,
            'rate_basis': 'job',
            'rate': 45000.0,
        })
        self.assertEqual(bill.amount, 45000.0)

    def test_amount_computation_per_hour(self):
        bill = self.env['sedar.towage.billing'].create({
            'job_order_id': self.job.id,
            'rate_basis': 'hour',
            'rate': 5000.0,
            'hours': 3.0,
        })
        self.assertEqual(bill.amount, 15000.0)

    def test_create_invoice_marks_job_billed(self):
        bill = self.env['sedar.towage.billing'].create({
            'job_order_id': self.job.id,
            'rate_basis': 'job',
            'rate': 30000.0,
        })
        bill.action_create_invoice()
        self.assertTrue(bill.invoice_id)
        self.assertEqual(bill.invoice_id.move_type, 'out_invoice')
        self.assertEqual(self.job.state, 'billed')
```

Add to `addons/sedar_tug_ops/tests/__init__.py`:
```python
from . import test_towage_billing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -u sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: FAIL — `sedar.towage.billing` doesn't exist.

- [ ] **Step 3: Write the model**

`addons/sedar_tug_ops/models/towage_billing.py`:
```python
from odoo import models, fields, api


class SedarTowageBilling(models.Model):
    _name = 'sedar.towage.billing'
    _description = 'Towage Billing'

    job_order_id = fields.Many2one('sedar.job.order', required=True)
    rate_basis = fields.Selection(
        [('hour', 'Per Hour'), ('job', 'Per Job')], default='job', required=True)
    rate = fields.Monetary(currency_field='currency_id')
    hours = fields.Float(string='Hours (if per-hour)')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(
        compute='_compute_amount', store=True, currency_field='currency_id')
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True, copy=False)

    @api.depends('rate_basis', 'rate', 'hours')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.rate * rec.hours if rec.rate_basis == 'hour' else rec.rate

    def action_create_invoice(self):
        self.ensure_one()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.job_order_id.customer_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': f'Towage service - {self.job_order_id.name}',
                'quantity': 1,
                'price_unit': self.amount,
            })],
        })
        self.invoice_id = invoice.id
        self.job_order_id.state = 'billed'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
        }
```

Update `addons/sedar_tug_ops/models/__init__.py`:
```python
from . import vessel
from . import job_order
from . import voyage_log
from . import fuel_log
from . import towage_billing
```

- [ ] **Step 4: Add views and menu**

`addons/sedar_tug_ops/views/towage_billing_views.xml`:
```xml
<odoo>
    <record id="view_sedar_towage_billing_list" model="ir.ui.view">
        <field name="name">sedar.towage.billing.list</field>
        <field name="model">sedar.towage.billing</field>
        <field name="arch" type="xml">
            <list>
                <field name="job_order_id"/>
                <field name="rate_basis"/>
                <field name="amount"/>
                <field name="invoice_id"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_towage_billing_form" model="ir.ui.view">
        <field name="name">sedar.towage.billing.form</field>
        <field name="model">sedar.towage.billing</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_create_invoice" string="Create Invoice"
                            type="object" invisible="invoice_id"/>
                </header>
                <sheet>
                    <group>
                        <field name="job_order_id"/>
                        <field name="rate_basis"/>
                        <field name="rate"/>
                        <field name="hours" invisible="rate_basis != 'hour'"/>
                        <field name="amount"/>
                        <field name="invoice_id" readonly="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_towage_billing" model="ir.actions.act_window">
        <field name="name">Towage Billing</field>
        <field name="res_model">sedar.towage.billing</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_tug_ops/views/menu.xml`:
```xml
<menuitem id="menu_towage_billing" name="Towage Billing" parent="menu_root"
          action="action_sedar_towage_billing" sequence="50"/>
```

- [ ] **Step 5: Add security row**

Append to `addons/sedar_tug_ops/security/ir.model.access.csv`:
```csv
access_sedar_towage_billing_user,sedar.towage.billing.user,model_sedar_towage_billing,base.group_user,1,1,1,1
```

- [ ] **Step 6: Register view file in manifest**

Add `'views/towage_billing_views.xml'` to the `data` list (before `views/menu.xml`).

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_tug_ops --test-enable --stop-after-init --log-level=test`
Expected: PASS. This completes `sedar_tug_ops`.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_tug_ops
git commit -m "feat(sedar_tug_ops): add Towage Billing with invoice creation"
```

---

### Task 7: `sedar_hsse` — Incidents + Near-Miss Reports

**Files:**
- Create: `addons/sedar_hsse/__init__.py`
- Create: `addons/sedar_hsse/__manifest__.py`
- Create: `addons/sedar_hsse/models/__init__.py`
- Create: `addons/sedar_hsse/models/incident.py`
- Create: `addons/sedar_hsse/models/near_miss.py`
- Create: `addons/sedar_hsse/views/incident_near_miss_views.xml`
- Create: `addons/sedar_hsse/views/menu.xml`
- Create: `addons/sedar_hsse/security/ir.model.access.csv`
- Test: `addons/sedar_hsse/tests/__init__.py`
- Test: `addons/sedar_hsse/tests/test_incident_near_miss.py`

**Interfaces:**
- Consumes: `sedar.vessel` (from `sedar_tug_ops`, Task 3).
- Produces: models `sedar.hsse.incident` (fields `name`, `date`, `vessel_id`, `location`, `severity`, `description`, `corrective_action`, `state`) and `sedar.hsse.near.miss` (fields `reporter_id`, `date`, `description`, `risk_category`). Root menu "HSSE" (`sedar_hsse.menu_root`).

- [ ] **Step 1: Create module skeleton**

`addons/sedar_hsse/__init__.py`:
```python
from . import models
```

`addons/sedar_hsse/__manifest__.py`:
```python
{
    'name': 'SEDAR HSSE',
    'version': '17.0.1.0.0',
    'summary': 'Incidents, near-miss, inspections, risk assessments, permits',
    'category': 'Operations',
    'depends': ['base', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/incident_near_miss_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
```

`addons/sedar_hsse/models/__init__.py`:
```python
from . import incident
from . import near_miss
```

- [ ] **Step 2: Write the failing test**

`addons/sedar_hsse/tests/__init__.py`:
```python
from . import test_incident_near_miss
```

`addons/sedar_hsse/tests/test_incident_near_miss.py`:
```python
from odoo.tests.common import TransactionCase


class TestIncidentNearMiss(TransactionCase):

    def test_create_incident(self):
        incident = self.env['sedar.hsse.incident'].create({
            'severity': 'medium',
            'description': 'Mooring line snapped during berthing at Batangas Port',
        })
        self.assertEqual(incident.state, 'open')

    def test_create_near_miss(self):
        near_miss = self.env['sedar.hsse.near.miss'].create({
            'description': 'Crew member nearly slipped on wet deck',
            'risk_category': 'personnel',
        })
        self.assertEqual(near_miss.risk_category, 'personnel')
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -i sedar_hsse --test-enable --stop-after-init --log-level=test`
Expected: FAIL — models don't exist yet.

- [ ] **Step 4: Write the models**

`addons/sedar_hsse/models/incident.py`:
```python
from odoo import models, fields, api


class SedarHsseIncident(models.Model):
    _name = 'sedar.hsse.incident'
    _description = 'HSSE Incident Report'
    _order = 'date desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    vessel_id = fields.Many2one('sedar.vessel')
    location = fields.Char()
    severity = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        required=True)
    description = fields.Text(required=True)
    corrective_action = fields.Text()
    state = fields.Selection(
        [('open', 'Open'), ('investigating', 'Investigating'), ('closed', 'Closed')],
        default='open', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sedar.hsse.incident') or 'New'
        return super().create(vals_list)
```

`addons/sedar_hsse/models/near_miss.py`:
```python
from odoo import models, fields


class SedarHsseNearMiss(models.Model):
    _name = 'sedar.hsse.near.miss'
    _description = 'Near-Miss Report'
    _order = 'date desc'

    reporter_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user, required=True)
    date = fields.Date(default=fields.Date.context_today)
    description = fields.Text(required=True)
    risk_category = fields.Selection(
        [('personnel', 'Personnel'), ('equipment', 'Equipment'), ('environment', 'Environment')])
```

- [ ] **Step 5: Add the incident sequence**

Create `addons/sedar_hsse/data/ir_sequence_data.xml`:
```xml
<odoo>
    <record id="seq_sedar_hsse_incident" model="ir.sequence">
        <field name="name">SEDAR HSSE Incident</field>
        <field name="code">sedar.hsse.incident</field>
        <field name="prefix">INC/%(year)s/</field>
        <field name="padding">4</field>
    </record>
</odoo>
```
Add `'data/ir_sequence_data.xml'` to the manifest `data` list (before the views).

- [ ] **Step 6: Add views and menu**

`addons/sedar_hsse/views/incident_near_miss_views.xml`:
```xml
<odoo>
    <record id="view_sedar_hsse_incident_list" model="ir.ui.view">
        <field name="name">sedar.hsse.incident.list</field>
        <field name="model">sedar.hsse.incident</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="date"/>
                <field name="vessel_id"/>
                <field name="severity"/>
                <field name="state"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_hsse_incident_form" model="ir.ui.view">
        <field name="name">sedar.hsse.incident.form</field>
        <field name="model">sedar.hsse.incident</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="date"/>
                        <field name="vessel_id"/>
                        <field name="location"/>
                        <field name="severity"/>
                        <field name="description"/>
                        <field name="corrective_action"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_hsse_incident" model="ir.actions.act_window">
        <field name="name">Incidents</field>
        <field name="res_model">sedar.hsse.incident</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_hsse_near_miss_list" model="ir.ui.view">
        <field name="name">sedar.hsse.near.miss.list</field>
        <field name="model">sedar.hsse.near.miss</field>
        <field name="arch" type="xml">
            <list>
                <field name="date"/>
                <field name="reporter_id"/>
                <field name="risk_category"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_hsse_near_miss_form" model="ir.ui.view">
        <field name="name">sedar.hsse.near.miss.form</field>
        <field name="model">sedar.hsse.near.miss</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="date"/>
                        <field name="reporter_id"/>
                        <field name="risk_category"/>
                        <field name="description"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_hsse_near_miss" model="ir.actions.act_window">
        <field name="name">Near-Miss Reports</field>
        <field name="res_model">sedar.hsse.near.miss</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

`addons/sedar_hsse/views/menu.xml`:
```xml
<odoo>
    <menuitem id="menu_root" name="HSSE" sequence="20"/>
    <menuitem id="menu_incident" name="Incidents" parent="menu_root"
              action="action_sedar_hsse_incident" sequence="10"/>
    <menuitem id="menu_near_miss" name="Near-Miss Reports" parent="menu_root"
              action="action_sedar_hsse_near_miss" sequence="20"/>
</odoo>
```

- [ ] **Step 7: Write security access**

`addons/sedar_hsse/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sedar_hsse_incident_user,sedar.hsse.incident.user,model_sedar_hsse_incident,base.group_user,1,1,1,1
access_sedar_hsse_near_miss_user,sedar.hsse.near.miss.user,model_sedar_hsse_near_miss,base.group_user,1,1,1,1
```

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_hsse --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add addons/sedar_hsse
git commit -m "feat(sedar_hsse): add Incident and Near-Miss reporting"
```

---

### Task 8: `sedar_hsse` — Inspections/Audits + Risk Assessments

**Files:**
- Modify: `addons/sedar_hsse/models/__init__.py`
- Create: `addons/sedar_hsse/models/inspection.py`
- Create: `addons/sedar_hsse/models/risk_assessment.py`
- Create: `addons/sedar_hsse/views/inspection_risk_views.xml`
- Modify: `addons/sedar_hsse/views/menu.xml`
- Modify: `addons/sedar_hsse/security/ir.model.access.csv`
- Modify: `addons/sedar_hsse/__manifest__.py`
- Test: `addons/sedar_hsse/tests/test_inspection_risk.py`
- Modify: `addons/sedar_hsse/tests/__init__.py`

**Interfaces:**
- Produces: models `sedar.hsse.inspection` (header, fields `name`, `inspection_type`, `auditor_id`, `date`, `line_ids`, `findings`) with child `sedar.hsse.inspection.line` (fields `inspection_id`, `item`, `result`, `remarks`), and `sedar.hsse.risk.assessment` (fields `activity`, `hazard`, `likelihood`, `severity`, computed `risk_score`, `mitigation`).

- [ ] **Step 1: Write the failing test**

`addons/sedar_hsse/tests/test_inspection_risk.py`:
```python
from odoo.tests.common import TransactionCase


class TestInspectionRisk(TransactionCase):

    def test_inspection_with_lines(self):
        inspection = self.env['sedar.hsse.inspection'].create({
            'inspection_type': 'vessel',
            'line_ids': [
                (0, 0, {'item': 'Fire extinguishers charged', 'result': 'pass'}),
                (0, 0, {'item': 'Life jackets count', 'result': 'fail',
                        'remarks': '2 missing'}),
            ],
        })
        self.assertEqual(len(inspection.line_ids), 2)
        self.assertEqual(inspection.line_ids[1].result, 'fail')

    def test_risk_score_computation(self):
        risk = self.env['sedar.hsse.risk.assessment'].create({
            'activity': 'Towing in heavy weather',
            'hazard': 'Line parting under load',
            'likelihood': '3',
            'severity': '4',
        })
        self.assertEqual(risk.risk_score, 12)
```

Add to `addons/sedar_hsse/tests/__init__.py`:
```python
from . import test_inspection_risk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -u sedar_hsse --test-enable --stop-after-init --log-level=test`
Expected: FAIL.

- [ ] **Step 3: Write the models**

`addons/sedar_hsse/models/inspection.py`:
```python
from odoo import models, fields


class SedarHsseInspection(models.Model):
    _name = 'sedar.hsse.inspection'
    _description = 'Inspection / Audit'
    _order = 'date desc'

    name = fields.Char(default='New', copy=False)
    inspection_type = fields.Selection([
        ('internal', 'Internal Audit'),
        ('regulatory', 'Regulatory Inspection'),
        ('vessel', 'Vessel Inspection'),
    ], required=True)
    auditor_id = fields.Many2one('res.users')
    date = fields.Date(default=fields.Date.context_today)
    line_ids = fields.One2many('sedar.hsse.inspection.line', 'inspection_id')
    findings = fields.Text()


class SedarHsseInspectionLine(models.Model):
    _name = 'sedar.hsse.inspection.line'
    _description = 'Inspection Checklist Line'

    inspection_id = fields.Many2one(
        'sedar.hsse.inspection', required=True, ondelete='cascade')
    item = fields.Char(required=True)
    result = fields.Selection([('pass', 'Pass'), ('fail', 'Fail')], default='pass')
    remarks = fields.Char()
```

`addons/sedar_hsse/models/risk_assessment.py`:
```python
from odoo import models, fields, api


class SedarHsseRiskAssessment(models.Model):
    _name = 'sedar.hsse.risk.assessment'
    _description = 'Risk Assessment'

    activity = fields.Char(required=True)
    hazard = fields.Text(required=True)
    likelihood = fields.Selection(
        [('1', 'Rare'), ('2', 'Unlikely'), ('3', 'Possible'),
         ('4', 'Likely'), ('5', 'Almost Certain')], default='3', required=True)
    severity = fields.Selection(
        [('1', 'Negligible'), ('2', 'Minor'), ('3', 'Moderate'),
         ('4', 'Major'), ('5', 'Catastrophic')], default='3', required=True)
    risk_score = fields.Integer(compute='_compute_risk_score', store=True)
    mitigation = fields.Text()

    @api.depends('likelihood', 'severity')
    def _compute_risk_score(self):
        for rec in self:
            rec.risk_score = int(rec.likelihood) * int(rec.severity)
```

Update `addons/sedar_hsse/models/__init__.py`:
```python
from . import incident
from . import near_miss
from . import inspection
from . import risk_assessment
```

- [ ] **Step 4: Add views and menu**

`addons/sedar_hsse/views/inspection_risk_views.xml`:
```xml
<odoo>
    <record id="view_sedar_hsse_inspection_list" model="ir.ui.view">
        <field name="name">sedar.hsse.inspection.list</field>
        <field name="model">sedar.hsse.inspection</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="inspection_type"/>
                <field name="auditor_id"/>
                <field name="date"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_hsse_inspection_form" model="ir.ui.view">
        <field name="name">sedar.hsse.inspection.form</field>
        <field name="model">sedar.hsse.inspection</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="inspection_type"/>
                        <field name="auditor_id"/>
                        <field name="date"/>
                    </group>
                    <notebook>
                        <page string="Checklist">
                            <field name="line_ids">
                                <list editable="bottom">
                                    <field name="item"/>
                                    <field name="result"/>
                                    <field name="remarks"/>
                                </list>
                            </field>
                        </page>
                        <page string="Findings">
                            <field name="findings"/>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_hsse_inspection" model="ir.actions.act_window">
        <field name="name">Inspections / Audits</field>
        <field name="res_model">sedar.hsse.inspection</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_hsse_risk_list" model="ir.ui.view">
        <field name="name">sedar.hsse.risk.assessment.list</field>
        <field name="model">sedar.hsse.risk.assessment</field>
        <field name="arch" type="xml">
            <list>
                <field name="activity"/>
                <field name="likelihood"/>
                <field name="severity"/>
                <field name="risk_score"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_hsse_risk_form" model="ir.ui.view">
        <field name="name">sedar.hsse.risk.assessment.form</field>
        <field name="model">sedar.hsse.risk.assessment</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="activity"/>
                        <field name="hazard"/>
                        <field name="likelihood"/>
                        <field name="severity"/>
                        <field name="risk_score"/>
                        <field name="mitigation"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_hsse_risk" model="ir.actions.act_window">
        <field name="name">Risk Assessments</field>
        <field name="res_model">sedar.hsse.risk.assessment</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_hsse/views/menu.xml`:
```xml
<menuitem id="menu_inspection" name="Inspections / Audits" parent="menu_root"
          action="action_sedar_hsse_inspection" sequence="30"/>
<menuitem id="menu_risk" name="Risk Assessments" parent="menu_root"
          action="action_sedar_hsse_risk" sequence="40"/>
```

- [ ] **Step 5: Add security rows**

Append to `addons/sedar_hsse/security/ir.model.access.csv`:
```csv
access_sedar_hsse_inspection_user,sedar.hsse.inspection.user,model_sedar_hsse_inspection,base.group_user,1,1,1,1
access_sedar_hsse_inspection_line_user,sedar.hsse.inspection.line.user,model_sedar_hsse_inspection_line,base.group_user,1,1,1,1
access_sedar_hsse_risk_user,sedar.hsse.risk.assessment.user,model_sedar_hsse_risk_assessment,base.group_user,1,1,1,1
```

- [ ] **Step 6: Register view file in manifest**

Add `'views/inspection_risk_views.xml'` to the `data` list (before `views/menu.xml`).

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_hsse --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_hsse
git commit -m "feat(sedar_hsse): add Inspections/Audits and Risk Assessments"
```

---

### Task 9: `sedar_hsse` — Permits (uses expiry mixin)

**Files:**
- Modify: `addons/sedar_hsse/models/__init__.py`
- Create: `addons/sedar_hsse/models/permit.py`
- Create: `addons/sedar_hsse/views/permit_views.xml`
- Modify: `addons/sedar_hsse/views/menu.xml`
- Modify: `addons/sedar_hsse/security/ir.model.access.csv`
- Modify: `addons/sedar_hsse/__manifest__.py`
- Modify: `addons/sedar_base/tests/test_expiry_mixin.py` (now runnable — no code change needed, just re-run)

**Interfaces:**
- Consumes: `sedar.expiry.mixin` (from `sedar_base`, Task 2).
- Produces: model `sedar.hsse.permit` (fields `name`, `permit_type`, `issuing_authority`, `issue_date`, plus inherited `expiry_date`/`expiry_status`).

- [ ] **Step 1: Write the model**

`addons/sedar_hsse/models/permit.py`:
```python
from odoo import models, fields


class SedarHssePermit(models.Model):
    _name = 'sedar.hsse.permit'
    _inherit = ['sedar.expiry.mixin']
    _description = 'HSSE Permit'

    name = fields.Char(required=True)
    permit_type = fields.Char()
    issuing_authority = fields.Selection([
        ('marina', 'MARINA'),
        ('pcg', 'Philippine Coast Guard'),
        ('ppa', 'Philippine Ports Authority'),
        ('other', 'Other'),
    ])
    issue_date = fields.Date()
```

Update `addons/sedar_hsse/models/__init__.py`:
```python
from . import incident
from . import near_miss
from . import inspection
from . import risk_assessment
from . import permit
```

Add `'sedar_base'` to `depends` in `addons/sedar_hsse/__manifest__.py` if not already present (it was added in Task 7 — verify).

- [ ] **Step 2: Add views and menu**

`addons/sedar_hsse/views/permit_views.xml`:
```xml
<odoo>
    <record id="view_sedar_hsse_permit_list" model="ir.ui.view">
        <field name="name">sedar.hsse.permit.list</field>
        <field name="model">sedar.hsse.permit</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="permit_type"/>
                <field name="issuing_authority"/>
                <field name="expiry_date"/>
                <field name="expiry_status"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_hsse_permit_form" model="ir.ui.view">
        <field name="name">sedar.hsse.permit.form</field>
        <field name="model">sedar.hsse.permit</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="permit_type"/>
                        <field name="issuing_authority"/>
                        <field name="issue_date"/>
                        <field name="expiry_date"/>
                        <field name="expiry_status" readonly="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_hsse_permit" model="ir.actions.act_window">
        <field name="name">Permits</field>
        <field name="res_model">sedar.hsse.permit</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_hsse/views/menu.xml`:
```xml
<menuitem id="menu_permit" name="Permits" parent="menu_root"
          action="action_sedar_hsse_permit" sequence="50"/>
```

- [ ] **Step 3: Add security row**

Append to `addons/sedar_hsse/security/ir.model.access.csv`:
```csv
access_sedar_hsse_permit_user,sedar.hsse.permit.user,model_sedar_hsse_permit,base.group_user,1,1,1,1
```

- [ ] **Step 4: Register view file in manifest**

Add `'views/permit_views.xml'` to the `data` list (before `views/menu.xml`).

- [ ] **Step 5: Install and run both this module's tests and the now-unblocked `sedar_base` mixin test**

Run: `docker compose exec odoo odoo -d sedar -u sedar_hsse,sedar_base --test-enable --stop-after-init --log-level=test`
Expected: PASS for all of `sedar_hsse`'s tests AND the three `test_expiry_mixin.py` tests written in Task 2 (`test_expired_status`, `test_warning_status`, `test_ok_status`).

- [ ] **Step 6: Commit**

```bash
git add addons/sedar_hsse
git commit -m "feat(sedar_hsse): add Permits using shared expiry mixin"
```

---

### Task 10: `sedar_crewing` — Crew Roster + Rotation Schedule

**Files:**
- Create: `addons/sedar_crewing/__init__.py`
- Create: `addons/sedar_crewing/__manifest__.py`
- Create: `addons/sedar_crewing/models/__init__.py`
- Create: `addons/sedar_crewing/models/crew_member.py`
- Create: `addons/sedar_crewing/models/rotation.py`
- Create: `addons/sedar_crewing/views/crew_rotation_views.xml`
- Create: `addons/sedar_crewing/views/menu.xml`
- Create: `addons/sedar_crewing/security/ir.model.access.csv`
- Test: `addons/sedar_crewing/tests/__init__.py`
- Test: `addons/sedar_crewing/tests/test_crew_rotation.py`

**Interfaces:**
- Consumes: `hr.employee` (Odoo core HR module), `sedar.vessel` (from `sedar_tug_ops`).
- Produces: models `sedar.crew.member` (fields `employee_id`, `rank`, `vessel_id`) and `sedar.crew.rotation` (fields `crew_id`, `vessel_id`, `onboard_date`, `offboard_date`, `state`). Root menu "Crewing" (`sedar_crewing.menu_root`).

- [ ] **Step 1: Create module skeleton**

`addons/sedar_crewing/__init__.py`:
```python
from . import models
```

`addons/sedar_crewing/__manifest__.py`:
```python
{
    'name': 'SEDAR Crewing',
    'version': '17.0.1.0.0',
    'summary': 'Crew scheduling, certifications, medicals, leave',
    'category': 'Human Resources',
    'depends': ['base', 'hr', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/crew_rotation_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
```

`addons/sedar_crewing/models/__init__.py`:
```python
from . import crew_member
from . import rotation
```

- [ ] **Step 2: Write the failing test**

`addons/sedar_crewing/tests/__init__.py`:
```python
from . import test_crew_rotation
```

`addons/sedar_crewing/tests/test_crew_rotation.py`:
```python
from odoo.tests.common import TransactionCase


class TestCrewRotation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({'name': 'Juan Dela Cruz'})
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Sipag'})

    def test_create_crew_member(self):
        crew = self.env['sedar.crew.member'].create({
            'employee_id': self.employee.id,
            'rank': 'Master',
            'vessel_id': self.vessel.id,
        })
        self.assertEqual(crew.employee_id, self.employee)

    def test_rotation_schedule(self):
        crew = self.env['sedar.crew.member'].create({
            'employee_id': self.employee.id,
            'rank': 'Chief Engineer',
        })
        rotation = self.env['sedar.crew.rotation'].create({
            'crew_id': crew.id,
            'vessel_id': self.vessel.id,
            'onboard_date': '2026-08-01',
        })
        self.assertEqual(rotation.state, 'scheduled')
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -i sedar_crewing --test-enable --stop-after-init --log-level=test`
Expected: FAIL.

- [ ] **Step 4: Write the models**

`addons/sedar_crewing/models/crew_member.py`:
```python
from odoo import models, fields


class SedarCrewMember(models.Model):
    _name = 'sedar.crew.member'
    _description = 'Crew Roster'

    employee_id = fields.Many2one('hr.employee', required=True)
    rank = fields.Char()
    vessel_id = fields.Many2one('sedar.vessel', string='Current Assignment')
```

`addons/sedar_crewing/models/rotation.py`:
```python
from odoo import models, fields


class SedarCrewRotation(models.Model):
    _name = 'sedar.crew.rotation'
    _description = 'Crew Rotation Schedule'
    _order = 'onboard_date desc'

    crew_id = fields.Many2one('sedar.crew.member', required=True)
    vessel_id = fields.Many2one('sedar.vessel', required=True)
    onboard_date = fields.Date(required=True)
    offboard_date = fields.Date()
    state = fields.Selection([
        ('scheduled', 'Scheduled'), ('onboard', 'On Board'), ('completed', 'Completed'),
    ], default='scheduled', required=True)
```

- [ ] **Step 5: Add views and menu**

`addons/sedar_crewing/views/crew_rotation_views.xml`:
```xml
<odoo>
    <record id="view_sedar_crew_member_list" model="ir.ui.view">
        <field name="name">sedar.crew.member.list</field>
        <field name="model">sedar.crew.member</field>
        <field name="arch" type="xml">
            <list>
                <field name="employee_id"/>
                <field name="rank"/>
                <field name="vessel_id"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_crew_member_form" model="ir.ui.view">
        <field name="name">sedar.crew.member.form</field>
        <field name="model">sedar.crew.member</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="employee_id"/>
                        <field name="rank"/>
                        <field name="vessel_id"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_crew_member" model="ir.actions.act_window">
        <field name="name">Crew Roster</field>
        <field name="res_model">sedar.crew.member</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_crew_rotation_list" model="ir.ui.view">
        <field name="name">sedar.crew.rotation.list</field>
        <field name="model">sedar.crew.rotation</field>
        <field name="arch" type="xml">
            <list>
                <field name="crew_id"/>
                <field name="vessel_id"/>
                <field name="onboard_date"/>
                <field name="offboard_date"/>
                <field name="state"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_crew_rotation_form" model="ir.ui.view">
        <field name="name">sedar.crew.rotation.form</field>
        <field name="model">sedar.crew.rotation</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="crew_id"/>
                        <field name="vessel_id"/>
                        <field name="onboard_date"/>
                        <field name="offboard_date"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_crew_rotation" model="ir.actions.act_window">
        <field name="name">Rotation Schedule</field>
        <field name="res_model">sedar.crew.rotation</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

`addons/sedar_crewing/views/menu.xml`:
```xml
<odoo>
    <menuitem id="menu_root" name="Crewing" sequence="30"/>
    <menuitem id="menu_crew_member" name="Crew Roster" parent="menu_root"
              action="action_sedar_crew_member" sequence="10"/>
    <menuitem id="menu_crew_rotation" name="Rotation Schedule" parent="menu_root"
              action="action_sedar_crew_rotation" sequence="20"/>
</odoo>
```

- [ ] **Step 6: Write security access**

`addons/sedar_crewing/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sedar_crew_member_user,sedar.crew.member.user,model_sedar_crew_member,base.group_user,1,1,1,1
access_sedar_crew_rotation_user,sedar.crew.rotation.user,model_sedar_crew_rotation,base.group_user,1,1,1,1
```

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_crewing --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_crewing
git commit -m "feat(sedar_crewing): add Crew Roster and Rotation Schedule"
```

---

### Task 11: `sedar_crewing` — Certifications + Medical Certificates + Leave

**Files:**
- Modify: `addons/sedar_crewing/models/__init__.py`
- Create: `addons/sedar_crewing/models/certification.py`
- Create: `addons/sedar_crewing/models/medical.py`
- Create: `addons/sedar_crewing/models/leave.py`
- Create: `addons/sedar_crewing/views/cert_medical_leave_views.xml`
- Modify: `addons/sedar_crewing/views/menu.xml`
- Modify: `addons/sedar_crewing/security/ir.model.access.csv`
- Test: `addons/sedar_crewing/tests/test_cert_medical_leave.py`
- Modify: `addons/sedar_crewing/tests/__init__.py`

**Interfaces:**
- Consumes: `sedar.expiry.mixin` (`sedar_base`), `sedar.crew.member` (Task 10).
- Produces: models `sedar.crew.certification` (fields `crew_id`, `cert_type`, `issue_date`, inherited expiry fields), `sedar.crew.medical` (fields `crew_id`, `exam_date`, `fit_for_duty`, inherited expiry fields), `sedar.crew.leave` (fields `crew_id`, `leave_type`, `date_from`, `date_to`, `state`, method `action_approve()`).

- [ ] **Step 1: Write the failing test**

`addons/sedar_crewing/tests/test_cert_medical_leave.py`:
```python
from odoo.tests.common import TransactionCase


class TestCertMedicalLeave(TransactionCase):

    def setUp(self):
        super().setUp()
        employee = self.env['hr.employee'].create({'name': 'Pedro Reyes'})
        self.crew = self.env['sedar.crew.member'].create({'employee_id': employee.id})

    def test_certification(self):
        cert = self.env['sedar.crew.certification'].create({
            'crew_id': self.crew.id,
            'cert_type': 'STCW Basic Safety Training',
        })
        self.assertEqual(cert.expiry_status, 'ok')

    def test_medical(self):
        medical = self.env['sedar.crew.medical'].create({
            'crew_id': self.crew.id,
            'fit_for_duty': True,
        })
        self.assertTrue(medical.fit_for_duty)

    def test_leave_approval(self):
        leave = self.env['sedar.crew.leave'].create({
            'crew_id': self.crew.id,
            'date_from': '2026-08-01',
            'date_to': '2026-08-10',
        })
        self.assertEqual(leave.state, 'draft')
        leave.action_approve()
        self.assertEqual(leave.state, 'approved')
```

Add to `addons/sedar_crewing/tests/__init__.py`:
```python
from . import test_cert_medical_leave
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -u sedar_crewing --test-enable --stop-after-init --log-level=test`
Expected: FAIL.

- [ ] **Step 3: Write the models**

`addons/sedar_crewing/models/certification.py`:
```python
from odoo import models, fields


class SedarCrewCertification(models.Model):
    _name = 'sedar.crew.certification'
    _inherit = ['sedar.expiry.mixin']
    _description = 'STCW Certification'

    crew_id = fields.Many2one('sedar.crew.member', required=True)
    cert_type = fields.Char(string='STCW Cert Type', required=True)
    issue_date = fields.Date()
```

`addons/sedar_crewing/models/medical.py`:
```python
from odoo import models, fields


class SedarCrewMedical(models.Model):
    _name = 'sedar.crew.medical'
    _inherit = ['sedar.expiry.mixin']
    _description = 'Medical Certificate'

    crew_id = fields.Many2one('sedar.crew.member', required=True)
    exam_date = fields.Date(default=fields.Date.context_today)
    fit_for_duty = fields.Boolean(default=True)
```

`addons/sedar_crewing/models/leave.py`:
```python
from odoo import models, fields


class SedarCrewLeave(models.Model):
    _name = 'sedar.crew.leave'
    _description = 'Crew Leave'

    crew_id = fields.Many2one('sedar.crew.member', required=True)
    leave_type = fields.Selection([
        ('vacation', 'Vacation'), ('sick', 'Sick'), ('emergency', 'Emergency'),
    ], default='vacation', required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('approved', 'Approved'), ('refused', 'Refused'),
    ], default='draft', required=True)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_refuse(self):
        self.write({'state': 'refused'})
```

Update `addons/sedar_crewing/models/__init__.py`:
```python
from . import crew_member
from . import rotation
from . import certification
from . import medical
from . import leave
```

Add `'sedar_base'` to `depends` in the manifest if not already listed (it was added in Task 10 — verify).

- [ ] **Step 4: Add views and menu**

`addons/sedar_crewing/views/cert_medical_leave_views.xml`:
```xml
<odoo>
    <record id="view_sedar_crew_cert_list" model="ir.ui.view">
        <field name="name">sedar.crew.certification.list</field>
        <field name="model">sedar.crew.certification</field>
        <field name="arch" type="xml">
            <list>
                <field name="crew_id"/>
                <field name="cert_type"/>
                <field name="expiry_date"/>
                <field name="expiry_status"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_crew_cert_form" model="ir.ui.view">
        <field name="name">sedar.crew.certification.form</field>
        <field name="model">sedar.crew.certification</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="crew_id"/>
                        <field name="cert_type"/>
                        <field name="issue_date"/>
                        <field name="expiry_date"/>
                        <field name="expiry_status" readonly="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_crew_cert" model="ir.actions.act_window">
        <field name="name">Certifications</field>
        <field name="res_model">sedar.crew.certification</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_crew_medical_list" model="ir.ui.view">
        <field name="name">sedar.crew.medical.list</field>
        <field name="model">sedar.crew.medical</field>
        <field name="arch" type="xml">
            <list>
                <field name="crew_id"/>
                <field name="exam_date"/>
                <field name="expiry_date"/>
                <field name="fit_for_duty"/>
                <field name="expiry_status"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_crew_medical_form" model="ir.ui.view">
        <field name="name">sedar.crew.medical.form</field>
        <field name="model">sedar.crew.medical</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="crew_id"/>
                        <field name="exam_date"/>
                        <field name="fit_for_duty"/>
                        <field name="expiry_date"/>
                        <field name="expiry_status" readonly="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_crew_medical" model="ir.actions.act_window">
        <field name="name">Medical Certificates</field>
        <field name="res_model">sedar.crew.medical</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_crew_leave_list" model="ir.ui.view">
        <field name="name">sedar.crew.leave.list</field>
        <field name="model">sedar.crew.leave</field>
        <field name="arch" type="xml">
            <list>
                <field name="crew_id"/>
                <field name="leave_type"/>
                <field name="date_from"/>
                <field name="date_to"/>
                <field name="state"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_crew_leave_form" model="ir.ui.view">
        <field name="name">sedar.crew.leave.form</field>
        <field name="model">sedar.crew.leave</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_approve" string="Approve" type="object"
                            invisible="state != 'draft'"/>
                    <button name="action_refuse" string="Refuse" type="object"
                            invisible="state != 'draft'"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="crew_id"/>
                        <field name="leave_type"/>
                        <field name="date_from"/>
                        <field name="date_to"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_crew_leave" model="ir.actions.act_window">
        <field name="name">Leave</field>
        <field name="res_model">sedar.crew.leave</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_crewing/views/menu.xml`:
```xml
<menuitem id="menu_crew_cert" name="Certifications" parent="menu_root"
          action="action_sedar_crew_cert" sequence="30"/>
<menuitem id="menu_crew_medical" name="Medical Certificates" parent="menu_root"
          action="action_sedar_crew_medical" sequence="40"/>
<menuitem id="menu_crew_leave" name="Leave" parent="menu_root"
          action="action_sedar_crew_leave" sequence="50"/>
```

- [ ] **Step 5: Add security rows**

Append to `addons/sedar_crewing/security/ir.model.access.csv`:
```csv
access_sedar_crew_cert_user,sedar.crew.certification.user,model_sedar_crew_certification,base.group_user,1,1,1,1
access_sedar_crew_medical_user,sedar.crew.medical.user,model_sedar_crew_medical,base.group_user,1,1,1,1
access_sedar_crew_leave_user,sedar.crew.leave.user,model_sedar_crew_leave,base.group_user,1,1,1,1
```

- [ ] **Step 6: Register view file in manifest**

Add `'views/cert_medical_leave_views.xml'` to the `data` list (before `views/menu.xml`).

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_crewing --test-enable --stop-after-init --log-level=test`
Expected: PASS. This completes `sedar_crewing`.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_crewing
git commit -m "feat(sedar_crewing): add Certifications, Medical Certificates, Leave"
```

---

### Task 12: `sedar_doccontrol` — Contracts + Vessel Certificates

**Files:**
- Create: `addons/sedar_doccontrol/__init__.py`
- Create: `addons/sedar_doccontrol/__manifest__.py`
- Create: `addons/sedar_doccontrol/models/__init__.py`
- Create: `addons/sedar_doccontrol/models/contract.py`
- Create: `addons/sedar_doccontrol/models/vessel_cert.py`
- Create: `addons/sedar_doccontrol/views/contract_vessel_cert_views.xml`
- Create: `addons/sedar_doccontrol/views/menu.xml`
- Create: `addons/sedar_doccontrol/security/ir.model.access.csv`
- Test: `addons/sedar_doccontrol/tests/__init__.py`
- Test: `addons/sedar_doccontrol/tests/test_contract_vessel_cert.py`

**Interfaces:**
- Consumes: `sedar.expiry.mixin` (`sedar_base`), `sedar.vessel` (`sedar_tug_ops`).
- Produces: models `sedar.doc.contract` (fields `name`, `partner_id`, `contract_type`, `effective_date`, `expiry_date`, `attachment_ids`) and `sedar.doc.vessel.cert` (fields `vessel_id`, `cert_type`, `issuing_body`, inherited expiry fields). Root menu "Document Control" (`sedar_doccontrol.menu_root`).

- [ ] **Step 1: Create module skeleton**

`addons/sedar_doccontrol/__init__.py`:
```python
from . import models
```

`addons/sedar_doccontrol/__manifest__.py`:
```python
{
    'name': 'SEDAR Document Control',
    'version': '17.0.1.0.0',
    'summary': 'Contracts, vessel certificates, insurance, permits, ISO docs',
    'category': 'Operations',
    'depends': ['base', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/contract_vessel_cert_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
```

`addons/sedar_doccontrol/models/__init__.py`:
```python
from . import contract
from . import vessel_cert
```

- [ ] **Step 2: Write the failing test**

`addons/sedar_doccontrol/tests/__init__.py`:
```python
from . import test_contract_vessel_cert
```

`addons/sedar_doccontrol/tests/test_contract_vessel_cert.py`:
```python
from odoo.tests.common import TransactionCase


class TestContractVesselCert(TransactionCase):

    def test_contract(self):
        partner = self.env['res.partner'].create({'name': 'PetroEnergy Fuels Inc.'})
        contract = self.env['sedar.doc.contract'].create({
            'name': 'Fuel Supply Agreement 2026',
            'partner_id': partner.id,
            'contract_type': 'Supply',
        })
        self.assertEqual(contract.partner_id, partner)

    def test_vessel_cert(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Bayani'})
        cert = self.env['sedar.doc.vessel.cert'].create({
            'vessel_id': vessel.id,
            'cert_type': 'Certificate of Vessel Registry',
        })
        self.assertEqual(cert.expiry_status, 'ok')
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -i sedar_doccontrol --test-enable --stop-after-init --log-level=test`
Expected: FAIL.

- [ ] **Step 4: Write the models**

`addons/sedar_doccontrol/models/contract.py`:
```python
from odoo import models, fields


class SedarDocContract(models.Model):
    _name = 'sedar.doc.contract'
    _description = 'Contract'

    name = fields.Char(required=True)
    partner_id = fields.Many2one('res.partner', string='Counterparty')
    contract_type = fields.Char()
    effective_date = fields.Date()
    expiry_date = fields.Date()
    attachment_ids = fields.Many2many('ir.attachment', string='Files')
```

`addons/sedar_doccontrol/models/vessel_cert.py`:
```python
from odoo import models, fields


class SedarDocVesselCert(models.Model):
    _name = 'sedar.doc.vessel.cert'
    _inherit = ['sedar.expiry.mixin']
    _description = 'Vessel Certificate'

    vessel_id = fields.Many2one('sedar.vessel', required=True)
    cert_type = fields.Char(required=True)
    issuing_body = fields.Char()
```

- [ ] **Step 5: Add views and menu**

`addons/sedar_doccontrol/views/contract_vessel_cert_views.xml`:
```xml
<odoo>
    <record id="view_sedar_doc_contract_list" model="ir.ui.view">
        <field name="name">sedar.doc.contract.list</field>
        <field name="model">sedar.doc.contract</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="partner_id"/>
                <field name="contract_type"/>
                <field name="expiry_date"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_doc_contract_form" model="ir.ui.view">
        <field name="name">sedar.doc.contract.form</field>
        <field name="model">sedar.doc.contract</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="partner_id"/>
                        <field name="contract_type"/>
                        <field name="effective_date"/>
                        <field name="expiry_date"/>
                        <field name="attachment_ids" widget="many2many_binary"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_doc_contract" model="ir.actions.act_window">
        <field name="name">Contracts</field>
        <field name="res_model">sedar.doc.contract</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_doc_vessel_cert_list" model="ir.ui.view">
        <field name="name">sedar.doc.vessel.cert.list</field>
        <field name="model">sedar.doc.vessel.cert</field>
        <field name="arch" type="xml">
            <list>
                <field name="vessel_id"/>
                <field name="cert_type"/>
                <field name="expiry_date"/>
                <field name="expiry_status"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_doc_vessel_cert_form" model="ir.ui.view">
        <field name="name">sedar.doc.vessel.cert.form</field>
        <field name="model">sedar.doc.vessel.cert</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="vessel_id"/>
                        <field name="cert_type"/>
                        <field name="issuing_body"/>
                        <field name="expiry_date"/>
                        <field name="expiry_status" readonly="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_doc_vessel_cert" model="ir.actions.act_window">
        <field name="name">Vessel Certificates</field>
        <field name="res_model">sedar.doc.vessel.cert</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

`addons/sedar_doccontrol/views/menu.xml`:
```xml
<odoo>
    <menuitem id="menu_root" name="Document Control" sequence="40"/>
    <menuitem id="menu_contract" name="Contracts" parent="menu_root"
              action="action_sedar_doc_contract" sequence="10"/>
    <menuitem id="menu_vessel_cert" name="Vessel Certificates" parent="menu_root"
              action="action_sedar_doc_vessel_cert" sequence="20"/>
</odoo>
```

- [ ] **Step 6: Write security access**

`addons/sedar_doccontrol/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sedar_doc_contract_user,sedar.doc.contract.user,model_sedar_doc_contract,base.group_user,1,1,1,1
access_sedar_doc_vessel_cert_user,sedar.doc.vessel.cert.user,model_sedar_doc_vessel_cert,base.group_user,1,1,1,1
```

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_doccontrol --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_doccontrol
git commit -m "feat(sedar_doccontrol): add Contracts and Vessel Certificates"
```

---

### Task 13: `sedar_doccontrol` — Insurance + Permits/Board Resolutions/ISO Docs

**Files:**
- Modify: `addons/sedar_doccontrol/models/__init__.py`
- Create: `addons/sedar_doccontrol/models/insurance.py`
- Create: `addons/sedar_doccontrol/models/doc_record.py`
- Create: `addons/sedar_doccontrol/views/insurance_doc_record_views.xml`
- Modify: `addons/sedar_doccontrol/views/menu.xml`
- Modify: `addons/sedar_doccontrol/security/ir.model.access.csv`
- Modify: `addons/sedar_doccontrol/__manifest__.py`
- Test: `addons/sedar_doccontrol/tests/test_insurance_doc_record.py`
- Modify: `addons/sedar_doccontrol/tests/__init__.py`

**Interfaces:**
- Consumes: `sedar.expiry.mixin` (`sedar_base`).
- Produces: models `sedar.doc.insurance` (fields `policy_no`, `insurer`, `coverage_type`, inherited expiry fields) and `sedar.doc.record` (fields `name`, `category` [`permit`/`board_resolution`/`iso`], `reference_no`, `attachment_ids`, `state`, inherited expiry fields).

- [ ] **Step 1: Write the failing test**

`addons/sedar_doccontrol/tests/test_insurance_doc_record.py`:
```python
from odoo.tests.common import TransactionCase


class TestInsuranceDocRecord(TransactionCase):

    def test_insurance(self):
        policy = self.env['sedar.doc.insurance'].create({
            'policy_no': 'MARINE-2026-0042',
            'insurer': 'Malayan Insurance',
            'coverage_type': 'Hull and Machinery',
        })
        self.assertEqual(policy.expiry_status, 'ok')

    def test_doc_record_categories(self):
        board_res = self.env['sedar.doc.record'].create({
            'name': 'Board Resolution No. 2026-05',
            'category': 'board_resolution',
        })
        iso_doc = self.env['sedar.doc.record'].create({
            'name': 'ISO 9001 Quality Manual',
            'category': 'iso',
        })
        self.assertEqual(board_res.category, 'board_resolution')
        self.assertEqual(iso_doc.state, 'active')
```

Add to `addons/sedar_doccontrol/tests/__init__.py`:
```python
from . import test_insurance_doc_record
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -u sedar_doccontrol --test-enable --stop-after-init --log-level=test`
Expected: FAIL.

- [ ] **Step 3: Write the models**

`addons/sedar_doccontrol/models/insurance.py`:
```python
from odoo import models, fields


class SedarDocInsurance(models.Model):
    _name = 'sedar.doc.insurance'
    _inherit = ['sedar.expiry.mixin']
    _description = 'Insurance Policy'

    policy_no = fields.Char(required=True)
    insurer = fields.Char()
    coverage_type = fields.Char()
```

`addons/sedar_doccontrol/models/doc_record.py`:
```python
from odoo import models, fields


class SedarDocRecord(models.Model):
    _name = 'sedar.doc.record'
    _inherit = ['sedar.expiry.mixin']
    _description = 'Permit / Board Resolution / ISO Document'

    name = fields.Char(required=True)
    category = fields.Selection([
        ('permit', 'Permit'),
        ('board_resolution', 'Board Resolution'),
        ('iso', 'ISO Document'),
    ], required=True)
    reference_no = fields.Char()
    attachment_ids = fields.Many2many('ir.attachment', string='Files')
    state = fields.Selection([
        ('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived'),
    ], default='active', required=True)
```

Update `addons/sedar_doccontrol/models/__init__.py`:
```python
from . import contract
from . import vessel_cert
from . import insurance
from . import doc_record
```

- [ ] **Step 4: Add views and menu**

`addons/sedar_doccontrol/views/insurance_doc_record_views.xml`:
```xml
<odoo>
    <record id="view_sedar_doc_insurance_list" model="ir.ui.view">
        <field name="name">sedar.doc.insurance.list</field>
        <field name="model">sedar.doc.insurance</field>
        <field name="arch" type="xml">
            <list>
                <field name="policy_no"/>
                <field name="insurer"/>
                <field name="coverage_type"/>
                <field name="expiry_date"/>
                <field name="expiry_status"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_doc_insurance_form" model="ir.ui.view">
        <field name="name">sedar.doc.insurance.form</field>
        <field name="model">sedar.doc.insurance</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="policy_no"/>
                        <field name="insurer"/>
                        <field name="coverage_type"/>
                        <field name="expiry_date"/>
                        <field name="expiry_status" readonly="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_doc_insurance" model="ir.actions.act_window">
        <field name="name">Insurance</field>
        <field name="res_model">sedar.doc.insurance</field>
        <field name="view_mode">list,form</field>
    </record>

    <record id="view_sedar_doc_record_list" model="ir.ui.view">
        <field name="name">sedar.doc.record.list</field>
        <field name="model">sedar.doc.record</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="category"/>
                <field name="reference_no"/>
                <field name="expiry_date"/>
                <field name="state"/>
            </list>
        </field>
    </record>
    <record id="view_sedar_doc_record_form" model="ir.ui.view">
        <field name="name">sedar.doc.record.form</field>
        <field name="model">sedar.doc.record</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="category"/>
                        <field name="reference_no"/>
                        <field name="expiry_date"/>
                        <field name="state"/>
                        <field name="attachment_ids" widget="many2many_binary"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_doc_record" model="ir.actions.act_window">
        <field name="name">Permits / Board Resolutions / ISO Docs</field>
        <field name="res_model">sedar.doc.record</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

Add to `addons/sedar_doccontrol/views/menu.xml`:
```xml
<menuitem id="menu_insurance" name="Insurance" parent="menu_root"
          action="action_sedar_doc_insurance" sequence="30"/>
<menuitem id="menu_doc_record" name="Permits / Resolutions / ISO Docs" parent="menu_root"
          action="action_sedar_doc_record" sequence="40"/>
```

- [ ] **Step 5: Add security rows**

Append to `addons/sedar_doccontrol/security/ir.model.access.csv`:
```csv
access_sedar_doc_insurance_user,sedar.doc.insurance.user,model_sedar_doc_insurance,base.group_user,1,1,1,1
access_sedar_doc_record_user,sedar.doc.record.user,model_sedar_doc_record,base.group_user,1,1,1,1
```

- [ ] **Step 6: Register view file in manifest**

Add `'views/insurance_doc_record_views.xml'` to the `data` list (before `views/menu.xml`).

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_doccontrol --test-enable --stop-after-init --log-level=test`
Expected: PASS. This completes `sedar_doccontrol`.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_doccontrol
git commit -m "feat(sedar_doccontrol): add Insurance and Permits/Resolutions/ISO Docs"
```

---

### Task 14: `sedar_dashboard` — KPI aggregation

**Files:**
- Create: `addons/sedar_dashboard/__init__.py`
- Create: `addons/sedar_dashboard/__manifest__.py`
- Create: `addons/sedar_dashboard/models/__init__.py`
- Create: `addons/sedar_dashboard/models/dashboard.py`
- Create: `addons/sedar_dashboard/views/dashboard_views.xml`
- Create: `addons/sedar_dashboard/views/menu.xml`
- Create: `addons/sedar_dashboard/security/ir.model.access.csv`
- Test: `addons/sedar_dashboard/tests/__init__.py`
- Test: `addons/sedar_dashboard/tests/test_dashboard.py`

**Interfaces:**
- Consumes: `sedar.job.order`, `sedar.vessel` (`sedar_tug_ops`); `sedar.hsse.incident`, `sedar.hsse.permit` (`sedar_hsse`); `sedar.crew.certification`, `sedar.crew.medical` (`sedar_crewing`); `sedar.doc.vessel.cert`, `sedar.doc.insurance`, `sedar.doc.record` (`sedar_doccontrol`); `account.move` (core `account`).
- Produces: model `sedar.dashboard` (non-persisted-feeling single snapshot record) with computed fields `active_jobs`, `vessel_utilization`, `open_incidents`, `expiring_documents`, `monthly_revenue`.

- [ ] **Step 1: Create module skeleton**

`addons/sedar_dashboard/__init__.py`:
```python
from . import models
```

`addons/sedar_dashboard/__manifest__.py`:
```python
{
    'name': 'SEDAR Management Dashboard',
    'version': '17.0.1.0.0',
    'summary': 'KPIs: fleet utilization, open incidents, expiring docs, revenue',
    'category': 'Operations',
    'depends': ['base', 'account', 'sedar_tug_ops', 'sedar_hsse', 'sedar_crewing',
                'sedar_doccontrol'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
```

`addons/sedar_dashboard/models/__init__.py`:
```python
from . import dashboard
```

- [ ] **Step 2: Write the failing test**

`addons/sedar_dashboard/tests/__init__.py`:
```python
from . import test_dashboard
```

`addons/sedar_dashboard/tests/test_dashboard.py`:
```python
from odoo.tests.common import TransactionCase


class TestDashboard(TransactionCase):

    def test_kpi_computation(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Diwata', 'status': 'active'})
        customer = self.env['res.partner'].create({'name': 'Cebu Stevedoring Corp'})
        self.env['sedar.job.order'].create({
            'customer_id': customer.id, 'vessel_id': vessel.id,
        })
        self.env['sedar.hsse.incident'].create({
            'severity': 'low', 'description': 'Minor deck slip, no injury',
        })

        board = self.env['sedar.dashboard'].create({})
        self.assertEqual(board.active_jobs, 1)
        self.assertEqual(board.open_incidents, 1)
        self.assertEqual(board.vessel_utilization, 100.0)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -i sedar_dashboard --test-enable --stop-after-init --log-level=test`
Expected: FAIL — `sedar.dashboard` doesn't exist.

- [ ] **Step 4: Write the model**

`addons/sedar_dashboard/models/dashboard.py`:
```python
from odoo import models, fields


class SedarDashboard(models.Model):
    _name = 'sedar.dashboard'
    _description = 'Management KPI Dashboard'

    name = fields.Char(default='SEDAR KPI Snapshot')
    active_jobs = fields.Integer(compute='_compute_kpis')
    vessel_utilization = fields.Float(compute='_compute_kpis', string='Vessel Utilization %')
    open_incidents = fields.Integer(compute='_compute_kpis')
    expiring_documents = fields.Integer(compute='_compute_kpis')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    monthly_revenue = fields.Monetary(compute='_compute_kpis', currency_field='currency_id')

    def _compute_kpis(self):
        job_order = self.env['sedar.job.order']
        vessel = self.env['sedar.vessel']
        incident = self.env['sedar.hsse.incident']
        invoice = self.env['account.move']
        expiry_models = [
            'sedar.hsse.permit', 'sedar.crew.certification', 'sedar.crew.medical',
            'sedar.doc.vessel.cert', 'sedar.doc.insurance', 'sedar.doc.record',
        ]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for rec in self:
            total_vessels = vessel.search_count([])
            active_vessels = vessel.search_count([('status', '=', 'active')])
            rec.active_jobs = job_order.search_count(
                [('state', 'not in', ['completed', 'billed'])])
            rec.vessel_utilization = (
                active_vessels / total_vessels * 100) if total_vessels else 0.0
            rec.open_incidents = incident.search_count([('state', '!=', 'closed')])
            rec.expiring_documents = sum(
                self.env[model].search_count(
                    [('expiry_status', 'in', ['warning', 'expired'])])
                for model in expiry_models
            )
            invoices = invoice.search([
                ('move_type', '=', 'out_invoice'),
                ('invoice_date', '>=', month_start),
                ('state', '=', 'posted'),
            ])
            rec.monthly_revenue = sum(invoices.mapped('amount_total'))
```

- [ ] **Step 5: Add views and menu**

`addons/sedar_dashboard/views/dashboard_views.xml`:
```xml
<odoo>
    <record id="view_sedar_dashboard_form" model="ir.ui.view">
        <field name="name">sedar.dashboard.form</field>
        <field name="model">sedar.dashboard</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group string="Fleet &amp; Operations">
                        <field name="active_jobs"/>
                        <field name="vessel_utilization"/>
                    </group>
                    <group string="Safety">
                        <field name="open_incidents"/>
                        <field name="expiring_documents"/>
                    </group>
                    <group string="Finance">
                        <field name="monthly_revenue"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_sedar_dashboard" model="ir.actions.act_window">
        <field name="name">KPI Dashboard</field>
        <field name="res_model">sedar.dashboard</field>
        <field name="view_mode">form</field>
        <field name="target">current</field>
    </record>
</odoo>
```

`addons/sedar_dashboard/views/menu.xml`:
```xml
<odoo>
    <menuitem id="menu_root" name="Management Dashboard"
              action="action_sedar_dashboard" sequence="50"/>
</odoo>
```

- [ ] **Step 6: Write security access**

`addons/sedar_dashboard/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sedar_dashboard_user,sedar.dashboard.user,model_sedar_dashboard,base.group_user,1,1,1,1
```

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_dashboard --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add addons/sedar_dashboard
git commit -m "feat(sedar_dashboard): add KPI dashboard aggregating all modules"
```

---

### Task 15: Configure native Odoo apps + link Maintenance to Vessel

**Files:**
- Create: `addons/sedar_maintenance_link/__init__.py`
- Create: `addons/sedar_maintenance_link/__manifest__.py`
- Create: `addons/sedar_maintenance_link/models/__init__.py`
- Create: `addons/sedar_maintenance_link/models/maintenance_equipment.py`
- Create: `addons/sedar_maintenance_link/views/maintenance_equipment_views.xml`
- Test: `addons/sedar_maintenance_link/tests/__init__.py`
- Test: `addons/sedar_maintenance_link/tests/test_maintenance_link.py`

**Interfaces:**
- Consumes: `maintenance.equipment` (core Odoo `maintenance` module), `sedar.vessel` (`sedar_tug_ops`).
- Produces: an added field `vessel_id` on `maintenance.equipment` so Technical/Maintenance work orders can be tied to a specific tugboat.

- [ ] **Step 1: Create module skeleton**

`addons/sedar_maintenance_link/__init__.py`:
```python
from . import models
```

`addons/sedar_maintenance_link/__manifest__.py`:
```python
{
    'name': 'SEDAR Maintenance-Vessel Link',
    'version': '17.0.1.0.0',
    'summary': 'Link Odoo Maintenance equipment records to SEDAR vessels',
    'category': 'Operations',
    'depends': ['maintenance', 'sedar_tug_ops'],
    'data': ['views/maintenance_equipment_views.xml'],
    'installable': True,
    'application': False,
}
```

`addons/sedar_maintenance_link/models/__init__.py`:
```python
from . import maintenance_equipment
```

- [ ] **Step 2: Write the failing test**

`addons/sedar_maintenance_link/tests/__init__.py`:
```python
from . import test_maintenance_link
```

`addons/sedar_maintenance_link/tests/test_maintenance_link.py`:
```python
from odoo.tests.common import TransactionCase


class TestMaintenanceLink(TransactionCase):

    def test_equipment_linked_to_vessel(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Bagwis'})
        equipment = self.env['maintenance.equipment'].create({
            'name': 'Main Engine - Port',
            'vessel_id': vessel.id,
        })
        self.assertEqual(equipment.vessel_id, vessel)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec odoo odoo -d sedar -i maintenance,sedar_maintenance_link --test-enable --stop-after-init --log-level=test`
Expected: FAIL — `vessel_id` field doesn't exist on `maintenance.equipment` yet.

- [ ] **Step 4: Write the inherited model**

`addons/sedar_maintenance_link/models/maintenance_equipment.py`:
```python
from odoo import models, fields


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
```

- [ ] **Step 5: Add the field to the equipment form view**

`addons/sedar_maintenance_link/views/maintenance_equipment_views.xml`:
```xml
<odoo>
    <record id="view_maintenance_equipment_form_inherit_sedar" model="ir.ui.view">
        <field name="name">maintenance.equipment.form.inherit.sedar</field>
        <field name="model">maintenance.equipment</field>
        <field name="inherit_id" ref="maintenance.hr_equipment_view_form"/>
        <field name="arch" type="xml">
            <field name="category_id" position="after">
                <field name="vessel_id"/>
            </field>
        </field>
    </record>
</odoo>
```

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose exec odoo odoo -d sedar -u sedar_maintenance_link --test-enable --stop-after-init --log-level=test`
Expected: PASS.

- [ ] **Step 7: Install and configure the remaining native apps manually (no code — Odoo Apps menu)**

Run: `docker compose exec odoo odoo -d sedar -i account,purchase,stock,hr,hr_recruitment --stop-after-init`
Expected: exits 0, no traceback. This installs Invoicing (`account`), Purchase, Inventory (`stock`), Employees (`hr`), and Recruitment (`hr_recruitment`) — the native apps identified in the spec's module map.

- [ ] **Step 8: Verify apps are installed and reachable**

Run: `docker compose exec odoo odoo -d sedar --stop-after-init` (sanity boot)
Log into `http://localhost:8069` as admin and confirm "Invoicing", "Purchase", "Inventory", "Employees", "Recruitment", "Maintenance" all appear in the apps switcher.

- [ ] **Step 9: Commit**

```bash
git add addons/sedar_maintenance_link
git commit -m "feat: link Maintenance equipment to vessels; install native Odoo apps"
```

---

### Task 16: Seed data script — Philippine demo data

**Files:**
- Create: `scripts/seed_data.py`
- Create: `scripts/README.md`

**Interfaces:**
- Consumes: every model produced in Tasks 3–15.
- Produces: a populated `sedar` database — at least 3 vessels, 2 customers, 3 job orders across different states, voyage logs, fuel logs, a towage bill with an invoice, HSSE incidents/near-misses/inspections/risks/permits, crew members with certifications/medicals/leave, contracts/vessel certs/insurance/doc records, and equipment linked to a vessel — so every tab has data to show in a demo.

- [ ] **Step 1: Write the seed script**

`scripts/seed_data.py`:
```python
"""Idempotent SEDAR demo-data seeder. Run inside the Odoo container shell.

Usage:
    docker compose exec odoo odoo shell -d sedar < scripts/seed_data.py
"""

def seed(env):
    Partner = env['res.partner']
    Vessel = env['sedar.vessel']
    JobOrder = env['sedar.job.order']
    VoyageLog = env['sedar.voyage.log']
    FuelLog = env['sedar.fuel.log']
    TowageBilling = env['sedar.towage.billing']
    Incident = env['sedar.hsse.incident']
    NearMiss = env['sedar.hsse.near.miss']
    Inspection = env['sedar.hsse.inspection']
    Risk = env['sedar.hsse.risk.assessment']
    Permit = env['sedar.hsse.permit']
    Employee = env['hr.employee']
    Crew = env['sedar.crew.member']
    Rotation = env['sedar.crew.rotation']
    Cert = env['sedar.crew.certification']
    Medical = env['sedar.crew.medical']
    Leave = env['sedar.crew.leave']
    Contract = env['sedar.doc.contract']
    VesselCert = env['sedar.doc.vessel.cert']
    Insurance = env['sedar.doc.insurance']
    DocRecord = env['sedar.doc.record']
    Equipment = env['maintenance.equipment']

    if Vessel.search_count([]):
        print('Seed data already present, skipping.')
        return

    vessels = Vessel.create([
        {'name': 'SEDAR Kalinga', 'registry_no': 'IMO-9123456',
         'vessel_type': 'tug', 'capacity': 3200.0, 'status': 'active'},
        {'name': 'SEDAR Bantay', 'registry_no': 'IMO-9123457',
         'vessel_type': 'tug', 'capacity': 2800.0, 'status': 'active'},
        {'name': 'SEDAR Tagumpay', 'registry_no': 'IMO-9123458',
         'vessel_type': 'barge', 'capacity': 5000.0, 'status': 'dry_dock'},
    ])

    customers = Partner.create([
        {'name': 'Manila South Harbor Terminal'},
        {'name': 'Batangas International Port Corp'},
    ])

    job1 = JobOrder.create({
        'customer_id': customers[0].id, 'vessel_id': vessels[0].id,
        'origin_port': 'Manila South Harbor', 'destination_port': 'Manila North Harbor',
        'state': 'completed',
    })
    JobOrder.create({
        'customer_id': customers[1].id, 'vessel_id': vessels[1].id,
        'origin_port': 'Batangas Port', 'destination_port': 'Subic Bay',
        'state': 'in_progress',
    })
    JobOrder.create({
        'customer_id': customers[0].id, 'vessel_id': vessels[0].id,
        'origin_port': 'Manila South Harbor', 'destination_port': 'Corregidor',
        'state': 'requested',
    })

    VoyageLog.create({
        'job_order_id': job1.id, 'distance_nm': 12.4,
        'weather_notes': 'Clear skies, calm seas',
    })
    FuelLog.create([
        {'vessel_id': vessels[0].id, 'liters': 850.0, 'cost': 62000.0},
        {'vessel_id': vessels[1].id, 'liters': 620.0, 'cost': 45000.0},
    ])
    bill = TowageBilling.create({
        'job_order_id': job1.id, 'rate_basis': 'job', 'rate': 45000.0,
    })
    bill.action_create_invoice()

    Incident.create({
        'severity': 'medium', 'vessel_id': vessels[1].id,
        'location': 'Batangas Port', 'description': 'Mooring line snapped during berthing',
        'corrective_action': 'Replaced line, briefed crew on load limits',
    })
    NearMiss.create({
        'description': 'Crew member nearly slipped on wet deck',
        'risk_category': 'personnel',
    })
    Inspection.create({
        'inspection_type': 'vessel',
        'line_ids': [
            (0, 0, {'item': 'Fire extinguishers charged', 'result': 'pass'}),
            (0, 0, {'item': 'Life jackets count', 'result': 'fail', 'remarks': '2 missing'}),
        ],
    })
    Risk.create({
        'activity': 'Towing in heavy weather', 'hazard': 'Line parting under load',
        'likelihood': '3', 'severity': '4', 'mitigation': 'Use higher-rated tow line',
    })
    Permit.create({
        'name': 'Certificate of Vessel Safety', 'permit_type': 'Safety',
        'issuing_authority': 'marina', 'expiry_date': '2026-12-31',
    })

    employees = Employee.create([
        {'name': 'Juan Dela Cruz'}, {'name': 'Pedro Reyes'},
    ])
    crew = Crew.create([
        {'employee_id': employees[0].id, 'rank': 'Master', 'vessel_id': vessels[0].id},
        {'employee_id': employees[1].id, 'rank': 'Chief Engineer', 'vessel_id': vessels[1].id},
    ])
    Rotation.create({
        'crew_id': crew[0].id, 'vessel_id': vessels[0].id, 'onboard_date': '2026-07-01',
    })
    Cert.create({
        'crew_id': crew[0].id, 'cert_type': 'STCW Basic Safety Training',
        'expiry_date': '2027-01-01',
    })
    Medical.create({'crew_id': crew[1].id, 'fit_for_duty': True, 'expiry_date': '2026-09-01'})
    Leave.create({
        'crew_id': crew[1].id, 'date_from': '2026-08-01', 'date_to': '2026-08-10',
    })

    Contract.create({
        'name': 'Fuel Supply Agreement 2026', 'partner_id': customers[0].id,
        'contract_type': 'Supply', 'expiry_date': '2027-06-30',
    })
    VesselCert.create({
        'vessel_id': vessels[0].id, 'cert_type': 'Certificate of Vessel Registry',
        'expiry_date': '2027-03-15',
    })
    Insurance.create({
        'policy_no': 'MARINE-2026-0042', 'insurer': 'Malayan Insurance',
        'coverage_type': 'Hull and Machinery', 'expiry_date': '2026-08-01',
    })
    DocRecord.create({
        'name': 'Board Resolution No. 2026-05', 'category': 'board_resolution',
    })

    Equipment.create({'name': 'Main Engine - Port', 'vessel_id': vessels[0].id})

    env.cr.commit()
    print('Seed data loaded successfully.')


seed(env)  # noqa: F821 -- `env` is injected by `odoo shell`
```

`scripts/README.md`:
```markdown
# Seed data

Run after all modules are installed:

    docker compose exec -T odoo odoo shell -d sedar < scripts/seed_data.py

Safe to re-run — exits early if vessels already exist.
```

- [ ] **Step 2: Run the seeder against the running stack**

Run: `docker compose exec -T odoo odoo shell -d sedar < scripts/seed_data.py`
Expected: prints `Seed data loaded successfully.`, no traceback.

- [ ] **Step 3: Verify data landed**

Run: `docker compose exec -T odoo odoo shell -d sedar -c "print(env['sedar.vessel'].search_count([]))"`
Expected: prints `3`.

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_data.py scripts/README.md
git commit -m "feat: add Philippine tugboat demo data seeder"
```

---

### Task 17: Screenshot walkthrough capture

**Files:**
- Create: `docs/walkthrough/README.md`
- Create: `docs/walkthrough/*.png` (one per tab, captured manually or via browser automation)

**Interfaces:**
- Consumes: the fully running, seeded instance from Tasks 1–16.
- Produces: a screenshot per menu/tab listed in the spec's module map, organized so the client demo can be given as a slide-free walkthrough of the actual system.

- [ ] **Step 1: Log into the running instance**

Navigate to `http://localhost:8069`, log in as `admin` (set password via the Odoo initial setup screen if not already set).

- [ ] **Step 2: Capture one screenshot per menu, in this exact order**

Create `docs/walkthrough/README.md` listing, in demo order, each screenshot filename and what it proves:

```markdown
# SEDAR MVP Walkthrough

1. 01-vessels.png — Tug Operations > Vessels (fleet roster)
2. 02-job-orders.png — Tug Operations > Job Orders (dispatch workflow, statusbar)
3. 03-voyage-log.png — Tug Operations > Voyage Log
4. 04-fuel-log.png — Tug Operations > Fuel Monitoring
5. 05-towage-billing.png — Tug Operations > Towage Billing (with linked invoice)
6. 06-incidents.png — HSSE > Incidents
7. 07-near-miss.png — HSSE > Near-Miss Reports
8. 08-inspections.png — HSSE > Inspections/Audits (checklist lines)
9. 09-risk.png — HSSE > Risk Assessments (computed risk score)
10. 10-permits.png — HSSE > Permits (expiry status column)
11. 11-crew-roster.png — Crewing > Crew Roster
12. 12-rotation.png — Crewing > Rotation Schedule
13. 13-certifications.png — Crewing > Certifications
14. 14-medical.png — Crewing > Medical Certificates
15. 15-leave.png — Crewing > Leave
16. 16-contracts.png — Document Control > Contracts
17. 17-vessel-certs.png — Document Control > Vessel Certificates
18. 18-insurance.png — Document Control > Insurance
19. 19-doc-records.png — Document Control > Permits/Resolutions/ISO Docs
20. 20-dashboard.png — Management Dashboard (KPIs)
21. 21-invoicing.png — Invoicing app > Customer Invoices
22. 22-purchase.png — Purchase app > Purchase Orders
23. 23-inventory.png — Inventory app > Products
24. 24-maintenance.png — Maintenance app > Equipment (vessel-linked)
25. 25-employees.png — Employees app
26. 26-recruitment.png — Recruitment app
```

- [ ] **Step 3: Save all screenshots to `docs/walkthrough/`**

Each PNG named exactly as listed above.

- [ ] **Step 4: Commit**

```bash
git add docs/walkthrough
git commit -m "docs: add MVP walkthrough screenshots for client demo"
```

This is the final task — the MVP is complete and demoable end-to-end.

---

## Self-Review Notes

**Spec coverage:** Every department and tab from the design spec has a corresponding task: Finance (Task 15, Invoicing), Tug Operations (Tasks 3–6), Technical/Maintenance (Task 15), HSSE (Tasks 7–9), Crewing (Tasks 10–11), Procurement (Task 15), Inventory (Task 15), HR (Task 15), Document Control (Tasks 12–13), Management Dashboard (Task 14). Demo data (Task 16) and client-facing walkthrough (Task 17) close the loop. Out-of-scope items from the spec (full GL, Payroll, AIS/GPS, Power BI, DocuSign, M365, mobile app) have no task — correctly, since they're explicitly deferred to Phase 2.

**Type consistency:** `sedar.job.order.state` values (`requested`/`dispatched`/`in_progress`/`completed`/`billed`) are used identically in Task 4 (definition), Task 6 (`action_create_invoice` sets `'billed'`), and Task 14 (dashboard filters `not in ['completed', 'billed']`). `sedar.expiry.mixin`'s `expiry_status` values (`ok`/`warning`/`expired`) are used identically in Task 2 (definition) and Task 14 (dashboard filters `in ['warning', 'expired']`).

**No placeholders:** all steps show complete, runnable code — no TBD/TODO markers.


