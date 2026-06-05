import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        entryFileNames: `chat-widget.js`,
        assetFileNames: `chat-widget.[ext]`
      }
    }
  }
})
