from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from engine_bioacustico import procesar_muestras_acusticas, generar_grafico_clinico, validar_audio
from reportes_pdf import generar_pdf_clinico

app = FastAPI(title="VocalisLab Bioacoustic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "engine": "Praat/Parselmouth + VOXplot ready"}


@app.post("/api/analizar-y-reportar")
async def analizar_y_reportar(
    audio_vocal: UploadFile = File(...),
    audio_habla: UploadFile = File(None),
    nombre: str = Form("Paciente Anónimo"),
    dni: str = Form("00000000"),
    edad: str = Form("30"),
    sexo: str = Form("Femenino"),
    motivo: str = Form("Evaluación vocal"),
    derivador: str = Form("Auto"),
    rasati: str = Form("{}"),
    tmf: float = Form(15.0)
):
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_vocal = os.path.join(tmp_dir, f"vocal_{audio_vocal.filename or 'a.wav'}")
    try:
        with open(tmp_vocal, "wb") as buffer:
            shutil.copyfileobj(audio_vocal.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al recibir archivo de audio: {str(e)}")

    try:
        audio_info = validar_audio(tmp_vocal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al validar audio: {str(e)}")

    if not audio_info["valid"]:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Audio no válido para análisis clínico",
                "issues": audio_info["issues"],
                "audio_info": {k: v for k, v in audio_info.items() if k != "issues"},
            }
        )

    try:
        metricas = procesar_muestras_acusticas(tmp_vocal)
        metricas["_file_path"] = tmp_vocal
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en el análisis bioacústico: {str(e)}")

    sintesis_ia = ""
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            avqi_str = str(metricas.get('avqi', 'N/D')) if metricas.get('avqi_calculable') else "no calculable"
            prompt = (
                f"Actúa como Fonoaudiólogo especialista en voz en Argentina. Redacta una síntesis interpretativa de los siguientes "
                f"resultados bioacústicos del paciente {nombre} ({edad} años, {sexo}). "
                f"NO emitas diagnóstico. Solo interpreta los valores objetivos:\n"
                f"- F0 media: {metricas['f0_mean']} Hz (mín: {metricas.get('f0_min', 'N/D')}, máx: {metricas.get('f0_max', 'N/D')})\n"
                f"- Jitter local: {metricas['jitter_pct']}%\n"
                f"- Shimmer local: {metricas['shimmer_pct']}% ({metricas.get('shimmer_db', 'N/D')} dB)\n"
                f"- HNR: {metricas['hnr_db']} dB\n"
                f"- CPPS: {metricas.get('cpps_db', 'N/D')} dB\n"
                f"- AVQI v03.01: {avqi_str}\n"
                f"Indica claramente que se trata de mediciones instrumentales que requieren correlación clínica. "
                f"Usa terminología formal en español rioplatense."
            )
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=400
            )
            sintesis_ia = chat_completion.choices[0].message.content
        except Exception as e:
            sintesis_ia = (
                f"Síntesis automática no disponible. "
                f"Los resultados bioacústicos fueron calculados correctamente, "
                f"pero no se pudo generar la interpretación asistida (Error: {str(e)})."
            )

    paciente_dict = {
        "nombre": nombre, "dni": dni, "edad": edad, "sexo": sexo,
        "motivo": motivo, "derivador": derivador,
        "sintesis_ia": sintesis_ia, "tmf": tmf
    }

    img_path = os.path.join(tmp_dir, "graficos_clinicos.png")
    pdf_path = os.path.join(tmp_dir, "informe_clinico.pdf")

    try:
        generar_grafico_clinico(metricas, img_path)
    except Exception as e:
        traceback.print_exc()
        img_path = ""

    try:
        generar_pdf_clinico(paciente_dict, metricas, img_path, pdf_path)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al generar el PDF: {str(e)}")

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer el PDF generado: {str(e)}")

    for p in [tmp_vocal, img_path, pdf_path]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    return Response(content=pdf_bytes, media_type="application/pdf")
