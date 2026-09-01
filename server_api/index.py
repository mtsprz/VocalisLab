from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import sys

# Agregar directorio actual al path para imports relativos en Vercel
sys.path.insert(0, os.path.dirname(__file__))

from engine_bioacustico import procesar_muestras_acusticas, generar_grafico_clinico
from reportes_pdf import generar_pdf_clinico

app = FastAPI(title="VocalisLab Serverless API")

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
    nombre: str = Form("Paciente Anonimo"),
    dni: str = Form("00000000"),
    edad: str = Form("30"),
    sexo: str = Form("Femenino"),
    motivo: str = Form("Evaluacion vocal"),
    derivador: str = Form("Auto"),
    rasati: str = Form("{}"),
    tmf: float = Form(15.0)
):
    tmp_vocal = f"/tmp/{audio_vocal.filename or 'vocal_a.wav'}"
    with open(tmp_vocal, "wb") as buffer:
        shutil.copyfileobj(audio_vocal.file, buffer)

    # 1. Calculo acustico deterministico
    metricas = procesar_muestras_acusticas(tmp_vocal)

    # 2. Generacion del grafico dual (DDF + Espectrograma)
    img_path = "/tmp/graficos_clinicos.png"
    generar_grafico_clinico(metricas, img_path)

    # 3. Sintesis diagnostica con Groq API (Llama 3.3 70B)
    groq_key = os.environ.get("GROQ_API_KEY")
    sintesis_ia = ""
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            prompt = (
                f"Actua como Fonoaudiologo especialista en voz en Argentina. Redacta una sintesis diagnostica fonoaudiologica formal y concisa "
                f"para el paciente {nombre} ({edad} anos, {sexo}). Metricas objetivas obtenidas: F0={metricas['f0_mean']} Hz, "
                f"AVQI={metricas['avqi']} (corte <=2.9), CPPS={metricas['cpps_db']} dB, Jitter={metricas['jitter_pct']}%, "
                f"Shimmer={metricas['shimmer_pct']}%, HNR={metricas['hnr_db']} dB, TMF={tmf} s. "
                f"Usa terminologia clinica formal en espanol rioplatense sin inventar datos."
            )
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=350
            )
            sintesis_ia = chat_completion.choices[0].message.content
        except Exception as e:
            sintesis_ia = f"Sintesis automatica: AVQI = {metricas['avqi']}. F0 = {metricas['f0_mean']} Hz. Error Groq: {str(e)}"

    # 4. Compilacion del PDF clinico formal
    pdf_path = "/tmp/informe_clinico.pdf"
    paciente_dict = {
        "nombre": nombre, "dni": dni, "edad": edad, "sexo": sexo,
        "motivo": motivo, "derivador": derivador,
        "sintesis_ia": sintesis_ia, "tmf": tmf
    }
    generar_pdf_clinico(paciente_dict, metricas, img_path, pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    return Response(content=pdf_bytes, media_type="application/pdf")
