# SEDAR Odoo Localhost Runbook

## Local URL

Open:

```text
http://localhost:8070/web/login
```

This machine uses port `8070` because another Odoo container already occupies `8069`.

## Login Credentials

```text
Username: username
Password: ppassword
```

## Start Localhost

From the `sedar` project folder:

```powershell
cd "C:\Users\Mann lee\Desktop\mann-projects\sedar"
$env:ODOO_PORT='8070'
docker compose up -d
```

## Check That It Is Running

```powershell
docker compose ps
curl.exe -sI http://localhost:8070/web/login
```

Expected result from `curl.exe`: `HTTP/1.0 200 OK` or `HTTP/1.1 200 OK`.

## Refresh After Code Changes

```powershell
docker compose exec odoo odoo -d sedar -u sedar_theme,sedar_tug_ops --stop-after-init
docker compose restart odoo
```

Then hard refresh the browser with `Ctrl + F5`.

## Stop Localhost

```powershell
docker compose down
```
