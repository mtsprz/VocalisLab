# VocalisLab - Deployment Checklist

## 1. Supabase Schema (DO FIRST)
- [ ] Go to https://supabase.com/dashboard/project/bkvfjnwglqfjlsivdttt/sql/new
- [ ] Copy content from `supabase/vocalislab_schema.sql`
- [ ] Paste and click **"Run"**

## 2. Deploy Backend to Render
- [ ] Go to https://dashboard.render.com/
- [ ] Click "New +" → "Web Service"
- [ ] Connect GitHub repo: `mtsprz/VocalisLab`
- [ ] Configure:
  - Name: `vocalislab-api`
  - Region: Oregon (US West)
  - Branch: `main`
  - Runtime: Docker
  - Dockerfile: `./Dockerfile`
  - Plan: Free
- [ ] Add env vars:
  - `GROQ_API_KEY` = `YOUR_GROQ_API_KEY`
  - `SUPABASE_URL` = `YOUR_SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY` = `YOUR_SUPABASE_SERVICE_ROLE_KEY`
- [ ] Wait for build (~2-3 min)
- [ ] Copy URL: `https://vocalislab-api.onrender.com`

## 3. Deploy Frontend to Vercel
- [ ] Go to https://vercel.com/mtsprz0-1278/new
- [ ] Import GitHub repo: `mtsprz/VocalisLab`
- [ ] Framework: Vite
- [ ] Add env vars:
  - `VITE_SUPABASE_URL` = `https://bkvfjnwglqfjlsivdttt.supabase.co`
  - `VITE_SUPABASE_ANON_KEY` = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrdmZqbndnaGxxZmpsc2l3ZHR0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgyMjYxMzcsImV4cCI6MjEwMzgwMjEzN30.qRT31x1XGBDlLHAbU8L65s7RdR42qKx636kLJLJ4xJ4`
  - `VITE_BACKEND_URL` = `https://vocalislab-api.onrender.com` (from step 2)
- [ ] Deploy
- [ ] Copy URL: `https://vocalislab.vercel.app`

## 4. Test
- [ ] Open frontend URL
- [ ] Record audio
- [ ] Check analysis results appear
- [ ] Check data saves to Supabase
