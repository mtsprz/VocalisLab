import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, './', '');
    return {
      server: {
        port: 3002,
        host: '0.0.0.0',
        proxy: {
          '/api': {
            target: 'http://localhost:3001',
            changeOrigin: true,
          },
        },
      },
      plugins: [react()],
       define: {
         'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY || env.GOOGLE_API_KEY || env.VITE_GOOGLE_API_KEY),
         'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY || env.GOOGLE_API_KEY || env.VITE_GOOGLE_API_KEY),
         'process.env.GOOGLE_API_KEY': JSON.stringify(env.GOOGLE_API_KEY || env.VITE_GOOGLE_API_KEY),
         'process.env.GROQ_API_KEY': JSON.stringify(env.GROQ_API_KEY || env.VITE_GROQ_API_KEY),
         'import.meta.env.VITE_GOOGLE_API_KEY': JSON.stringify(env.VITE_GOOGLE_API_KEY || env.GOOGLE_API_KEY),
         'import.meta.env.VITE_BACKEND_URL': JSON.stringify(env.VITE_BACKEND_URL || ''),
         'import.meta.env.VITE_VAPID_PUBLIC_KEY': JSON.stringify(env.VAPID_PUBLIC_KEY || 'BL7NdgwOxVxcPyIhthBht6s8BNB2cDj5CyCY_vPvUY7cq1AFu1VmHg116iYRMiWkRNCvaeC7lTfqOIlHoQ1EFSs'),
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      },
      build: {
        ssr: false,  // FORCE SPA-only build (no SSR functions that bundle googleapis with >>> tokens)
        rollupOptions: {
          output: {
            manualChunks: {
              vendor: ['react', 'react-dom'],
              supabase: ['@supabase/supabase-js'],
            },
            chunkFileNames: 'assets/[hash].js',
            entryFileNames: 'assets/[hash].js',
            assetFileNames: 'assets/[hash].[ext]'
          }
        },
        target: 'esnext',
        cssCodeSplit: true,
        sourcemap: false,
        chunkSizeWarningLimit: 2000,
        minify: 'esbuild', // más rápido que terser → build Vite ~7min vs 14min; entra límite Vercel
        reportCompressedSize: false,
      }
    };
});
