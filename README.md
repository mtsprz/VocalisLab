# FonoAudio-Pro AI 🧠

FonoAudio-Pro es una plataforma clínica avanzada diseñada para fonoaudiólogos, que integra inteligencia artificial generativa (Gemini 1.5 Flash) para asistir en el razonamiento clínico, la planificación de tratamientos y la síntesis de informes.

## ✨ Características Principales

- **Modo Planificación Clínica Asistida**: Análisis multimodal que procesa la ficha del paciente, historial de sesiones, evaluaciones y documentos adjuntos (imágenes/PDFs) para generar hipótesis clínicas, objetivos y un borrador de plan de tratamiento.
- **Síntesis de Informes Inteligente (RAG)**: Generación de informes profesionales utilizando plantillas estructuradas y la información clínica del paciente mediante técnicas de Generación Aumentada por Recuperación.
- **Integración Multimodal**: Capacidad de analizar documentos escaneados directamente mediante visión artificial para extraer datos relevantes.
- **Gestión de Agenda y Teleatención**: Integración con Google Calendar y Google Meet para la gestión de turnos y sesiones virtuales.
- **Automatización con n8n**: Sincronización de resultados de investigación y consultas de NotebookLM con flujos de trabajo externos.
- **Asistente de Voz**: Interacción por voz para la toma de notas y comandos rápidos.
- **Biblioteca de Materiales**: Gestión de recursos educativos y terapéuticos.

## 🚀 Tecnologías Utilizadas

- **Frontend**: React, TypeScript, Tailwind CSS, Lucide React, Recharts.
- **Backend**: Node.js, Express.
- **IA**: Google Gemini 1.5 Flash (Multimodal Reasoning & RAG).
- **Base de Datos**: Supabase (PostgreSQL).
- **Integraciones**: Google Workspace (Calendar, Meet, Drive), n8n, Obsidian (vía Local REST API).
- **TTS/STT**: Piper (Local TTS) y Web Speech API.

## 🛠️ Instalación y Configuración

### Requisitos previos
- Node.js (v18+)
- Supabase cuenta configurada.
- Google Cloud Console (para API de Gemini y Google Workspace).
- n8n (opcional, para automatizaciones).

### Configuración del Entorno

1. Clonar el repositorio.
2. Configurar el archivo `.env` con las siguientes claves (ver `.env.example`):
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
   - `GOOGLE_API_KEY`
   - `VITE_BACKEND_URL`
   - `TELEGRAM_BOT_TOKEN` (opcional)
   - `TELEGRAM_CHAT_ID` (opcional)
   - `OBSIDIAN_API_KEY` (opcional)
   - `OBSIDIAN_URL` (opcional)

3. Instalar dependencias:
   ```bash
   npm install
   ```

4. Ejecutar el servidor backend:
   ```bash
   node fonoaudio-server.js
   ```

5. Ejecutar la aplicación frontend:
   ```bash
   npm run dev
   ```

## 📂 Estructura del Proyecto

- `components/`: Componentes de la interfaz de usuario.
- `routes/`: Rutas de la API de Express.
- `services/`: Lógica de negocio y servicios de IA.
- `utils/`: Funciones de utilidad (Gemini, herramientas de IA).
- `extracted_texts/`: Almacenamiento de plantillas de informes.
- `supabase/`: Esquemas de la base de datos.

---
*Desarrollado para optimizar la práctica clínica fonoaudiológica mediante IA.*
