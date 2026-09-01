# Deploy to Render

1. Go to https://dashboard.render.com/
2. Click **"New +"** → **"Web Service"**
3. Connect GitHub repo: `mtsprz/VocalisLab`
4. Configure:
   - **Name**: `vocalislab-api`
   - **Region**: `Oregon (US West)`
   - **Branch**: `main`
   - **Root Directory**: leave blank
   - **Runtime**: `Docker`
   - **Dockerfile**: `./Dockerfile`
   - **Plan**: Free
5. Add Environment Variables:
   - `GROQ_API_KEY` = `YOUR_GROQ_API_KEY`
   - `SUPABASE_URL` = `YOUR_SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY` = `YOUR_SUPABASE_SERVICE_ROLE_KEY`
6. Click **"Create Web Service"**
7. Wait for build (~2-3 min)
8. Copy the URL: `https://vocalislab-api.onrender.com`
