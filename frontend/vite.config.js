import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import process from 'node:process'

const BACKEND_PORT = process.env.BACKEND_PORT || 9000;
const FRONTEND_PORT = process.env.FRONTEND_PORT || 7500;

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (_proxyReq, req) => {
            console.log('Sending Request:', req.url);
          });
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log('Received Response:', proxyRes.statusCode, req.url);
          });
        }
      }
    }
  }
})
