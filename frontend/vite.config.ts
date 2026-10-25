import { createHash } from 'node:crypto';
import path from 'node:path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

const securityHeaders = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, 'VITE_');
  const apiOrigin = env.VITE_API_URL && /^https?:\/\//.test(env.VITE_API_URL)
    ? new URL(env.VITE_API_URL).origin : '';
  return {
    base: process.env.BASE_PATH || '/',
    plugins: [react(), tailwindcss(), {
      name: 'production-content-security-policy',
      apply: 'build',
      transformIndexHtml: {
        order: 'post',
        handler(html) {
          const hashes = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
            .map(([, source]) => `'sha256-${createHash('sha256').update(source).digest('base64')}'`);
          const policy = [
            "default-src 'self'", `script-src 'self' ${hashes.join(' ')}`,
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com", "img-src 'self' data: blob:",
            `connect-src 'self' ${apiOrigin}`, "object-src 'none'", "base-uri 'self'",
            "form-action 'self'",
          ].join('; ');
          return html.replace('<head>', `<head>\n    <meta http-equiv="Content-Security-Policy" content="${policy}">`);
        },
      },
    }],
    resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
    server: { host: '127.0.0.1', port: Number(process.env.PORT || 5173), strictPort: true, headers: securityHeaders },
    preview: { host: '127.0.0.1', headers: securityHeaders },
    build: { outDir: 'dist' },
  };
});
