# SEDAR Engine Room (frontend)

React 19 + TypeScript + Vite + Tailwind 4 source of the Daily Engine Monitoring Report page that the crew uses aboard.
The layout and components come from Ed's prototype (https://github.com/EdrianHernandez/sedar-layout, Chief Engineer section, commit 1e89fd1); the mock data is replaced by the Odoo endpoints in `src/api.ts`.

Two builds come from the same source and are committed under `custom-addons/marine/sedar_marine_maintenance/static/engine_room`:

- `embed.js` is what users get: Technical Maintenance > Daily Engine Reports is an Odoo client action (`static/src/js/engine_room_action.js`) that mounts the app inside Odoo's own screen, in a shadow root so Ed's CSS cannot touch Odoo's. Odoo supplies the navbar and sidebar, so only a slim toolbar is drawn.
- `index.html` is a standalone copy with its own sidebar and a service worker, for the crew when Odoo itself cannot load. It is not linked from Odoo.

Rules live in the `sedar.daily.engine.report` model; this app only collects and shows data.

```bash
npm install
npm run lint && npm run build   # type-checks, then writes both bundles into the addon
```

Rebuild and commit the bundle after every change. When a release must reach devices that already cached the page, bump `CACHE` in `public/sw.js`.
