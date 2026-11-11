import { defineConfig } from 'vite';

// Dev: Vite serves the UI on :5173 and proxies API calls to the Python
// backend on :8787. Production: `npm run build` -> dist/, which the
// Python server serves directly (single process, one port).
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8787',
    },
  },
});
