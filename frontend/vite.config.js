import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  base: '/static/react/',
  build: {
    outDir: '../newspulse/src/newspulse/web/static/react',
    emptyOutDir: true,
    manifest: true,
    rolldownOptions: { input: {desk: fileURLToPath(new URL('./src/desk.jsx', import.meta.url)), twin: fileURLToPath(new URL('./src/twin.jsx', import.meta.url))} },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.js'] },
});
