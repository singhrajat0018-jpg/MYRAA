import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 3000,
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true'
        ? null
        : {
            // Backend/runtime-generated files only. Never ignore frontend
            // source - HMR must keep working for src/**.
            ignored: [
              '**/runtime/**',
              '**/*.tmp',
              '**/*.bak',
              '**/*.corrupt.*',
              '**/myraa_brain_memory.json',
              '**/secrets.json',
              '**/*.log',
            ],
          },
    },
  };
});
