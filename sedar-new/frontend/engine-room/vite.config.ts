import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../../custom-addons/marine/sedar_marine_maintenance/static/engine_room',
    emptyOutDir: true,
  },
})
