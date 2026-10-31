import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = { '/api': { target: env.MAEUM_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } };
  proxy['/v4'] = {target: env.MAEUM_API_TARGET || 'http://127.0.0.1:8000', changeOrigin:true};
  return { plugins: [react()], server: { proxy }, preview: { proxy } };
});
