# SEDAR Odoo 19 Development Workspace

This workspace is prepared for an Odoo 19.0 development environment.

## Layout

- `config/` - Odoo configuration
- `custom-addons/` - SEDAR custom modules
- `data/` - local PostgreSQL and Odoo data mounts
- `docker-compose.yml` - Odoo 19 and PostgreSQL services

## Start

Docker Desktop must be running before starting the stack.

```powershell
docker compose up -d
```

Then open http://localhost:8069.

The default development database credentials are defined in `docker-compose.yml` and
`config/odoo.conf`. Change them before using this outside a local development machine.

## Document Intake Workflow

Every SEDAR source form follows this sequence:

1. **Extract content completely** - inspect the supplied PDF or image and transcribe every visible item, including metadata, fields, instructions, statements, confidentiality notices, checkbox options, table labels, signature labels, and closing text. Do not summarize or omit content. Mark genuinely unreadable text as `[unclear]` for confirmation.
2. **Wait for approval** - present the extraction for business-owner confirmation.
3. **Add planning catalogue** - record the approved definition under `documents/`.
4. **Add to Odoo Documents module** - add the metadata, field definition, and approved source file to `sedar_document_control`.

The first two approved entries are ADM-2 and ADM-3. The custom addon creates the SEDAR menu,
Document Catalogue, Typed Template Fields, Controlled Documents, and Employee Document Requests.
It loads the approved source PDFs and typed field templates when installed.

## Fillable Document Workflow

1. Open **SEDAR > Document Control > Employee Document Requests**.
2. Create a request and select a document template such as ADM-5.
3. Enter the applicant or employee and assigned HR user.
4. Open the **Fillable Form** tab. The request generates the template's typed fields automatically.
5. Enter text, dates, whole numbers, decimal numbers, selections, Yes/No answers, signatures, and uploaded attachments in their corresponding controls.
6. Use **Submit**. Odoo blocks submission when a required field is incomplete.
7. HR reviews and approves or rejects the request.

The template's **Typed Template Fields** menu shows each field's expected data type. The original
PDF remains available under **Controlled Documents** as the source/reference copy.

After Docker Desktop is running, initialize the demo database and install the addon:

```powershell
docker compose up -d
docker compose exec odoo odoo -d sedar_demo -i base,sedar_document_control --without-demo=all --stop-after-init
docker compose restart odoo
```

Then open `http://localhost:8069` and select the `sedar_demo` database.
