# VocalisLab — Plataforma Fonoaudiológica de Análisis Acústico y Bioacústica Avanzada

VocalisLab es una aplicación web fonoaudiológica de alta precisión diseñada para la evaluación objetiva de la voz patológica y normovoz, integrando estándares científicos internacionales y algoritmos determinísticos.

## Arquitectura del Sistema (Monorepo Serverless)

- **Frontend (PWA):** React + Vite + Tailwind CSS + Web Audio API. Permite la selección de interfaces de audio externas (placas de audio USB / profesionales) y la grabación de muestras clínicas de alta fidelidad a 44.1 kHz PCM sin pérdidas.
- **Backend Bioacústico (FastAPI Serverless):** Desplegado en Vercel (`/api/`), encargado del procesamiento digital de señales con `praat-parselmouth` (Python).
- **Motores y Métricas Clínicas:**
  - **Praat / Parselmouth:** Extracción automatizada de $F_0$ (Frecuencia Fundamental), Jitter local, Shimmer local, HNR (Harmonics-to-Noise Ratio).
  - **AVQI v03.01:** Cálculo oficial del *Acoustic Voice Quality Index* versión 3.01 (Maryn et al.) combinando perturbaciones y armónicos.
  - **VoxMetria / VOXplot:** Estimación de CPPS (Cepstral Peak Prominence Smoothed) y generación de gráficos duales (Diagrama de Desviación Fonatoria - DDF y Espectrograma de Banda Estrecha).
- **Inteligencia Clínica (Groq API):** Integración con `llama-3.3-70b-versatile` procesando exclusivamente datos numéricos para redactar la síntesis diagnóstica en **español rioplatense** con terminología fonoaudiológica formal.
- **Reportes Formales (ReportLab):** Generación de informes en PDF acreditando el origen de cada métrica (Praat, VOXplot, VoxMetria).
- **Persistencia (Supabase):** Resguardo estructurado de pacientes, historiales de evaluaciones vocales y almacenamiento seguro de archivos WAV a 44.1 kHz en buckets dedicados.

---

## Estructura del Repositorio

```
VocalisLab/
├── api/
│   ├── index.py              # Endpoint principal FastAPI (Serverless Vercel)
│   ├── engine_bioacustico.py # Procesamiento Parselmouth, AVQI v03.01 y DDF
│   ├── reportes_pdf.py       # Generador de informes formales con ReportLab
│   └── requirements.txt      # Dependencias de Python
├── components/
│   └── VocalisLabModule.tsx  # Interfaz PWA, grabador y selector de placas de audio
├── supabase/
│   └── vocalislab_schema.sql # Esquema SQL (pacientes, evaluaciones y buckets)
├── vercel.json               # Enrutamiento unificado monorepo para Vercel
└── package.json              # Dependencias del Frontend React/Vite
```

---

## Configuración y Variables de Entorno

Configura las siguientes variables en tu panel de Vercel (`Settings > Environment Variables`):

| Variable | Descripción |
| :--- | :--- |
| `GROQ_API_KEY` | Clave de Groq Cloud para la síntesis diagnóstica con Llama 3.3 70B |
| `VITE_SUPABASE_URL` | URL de conexión al proyecto Supabase |
| `VITE_SUPABASE_ANON_KEY` | Llave anónima pública de Supabase |
