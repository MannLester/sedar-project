import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/sedar_marine_maintenance/static/engine_room/',
  plugins: [react(), tailwindcss()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: '../../custom-addons/marine/sedar_marine_maintenance/static/engine_room',
    emptyOutDir: false,
    publicDir: false,
    assetsInlineLimit: 0,
    lib: { entry: 'src/embed.tsx', name: 'SedarEngineRoom', formats: ['iife'], fileName: () => 'embed.js' },
  },
})
