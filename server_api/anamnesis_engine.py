"""
VocalisLab Pro — Anamnesis Inteligente
Endpoint para transcripción Whisper + estructuración LLM + muestra vocal.
"""
import os
import sys
import json
import tempfile
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

try:
    from groq import Groq
except ImportError:
    Groq = None

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = None
if GROQ_KEY and Groq:
    groq_client = Groq(api_key=GROQ_KEY)


def transcribir_audio_groq(audio_bytes: bytes, filename: str) -> dict:
    if not groq_client:
        return {"error": "Groq no configurado", "transcripcion": ""}
    try:
        suffix = ".wav"
        if filename.lower().endswith(".webm"):
            suffix = ".webm"
        elif filename.lower().endswith(".mp3"):
            suffix = ".mp3"
        elif filename.lower().endswith(".ogg"):
            suffix = ".ogg"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            result = groq_client.audio.transcriptions.create(
                file=(filename, f),
                model="whisper-large-v3",
                language="es",
                response_format="verbose_json",
            )

        os.unlink(tmp_path)

        return {
            "transcripcion": result.text if hasattr(result, "text") else "",
            "duracion_s": result.duration if hasattr(result, "duration") else 0,
            "language": result.language if hasattr(result, "language") else "es",
        }
    except Exception as e:
        return {"error": str(e), "transcripcion": ""}


ANAMNESIS_SYSTEM_PROMPT = """Eres un asistente de fonoaudiología clínica. Analiza la transcripción de una anamnesis vocal y extrae información estructurada.

Responde ÚNICAMENTE con JSON válido con esta estructura exacta:
{
  "motivo_consulta": "descripción del motivo principal",
  "diagnostico_orl": "diagnóstico ORL si se menciona, o null",
  "metodo_exploracion": "método de exploración vocal usado",
  "sintomas": {
    "disfonia": true/false,
    "dolor": true/false,
    "fatiga_vocal": true/false,
    "tos_cronica": true/false,
    "reflujo": true/false,
    "sensacion_nudo_garganta": true/false,
    "perdida_voz": true/false,
    "carraspeo": true/false,
    "sequedad": true/false
  },
  "factores_riesgo": {
    "tabaquismo": true/false,
    "reflujo_gastroesofagico": true/false,
    "uso_vocal_intenso": true/false,
    "ruido_ambiental": true/false,
    "medicamentos": "",
    "otros": ""
  },
  "resumen_clinico": "resumen de 2-3 líneas para el historial clínico"
}

Si no hay información suficiente para un campo, usa false para booleanos y null para strings.
NO incluyas explicaciones fuera del JSON."""


def estructurar_anamnesis_llm(transcripcion: str) -> dict:
    if not groq_client:
        return {"error": "Groq no configurado"}

    try:
        from llm_client import groq_chat
        raw, _model = groq_chat(
            messages=[
                {"role": "system", "content": ANAMNESIS_SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcripción de anamnesis vocal:\n\n{transcripcion}"},
            ],
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        raw = raw.strip()
        parsed = json.loads(raw)
        return parsed

    except json.JSONDecodeError:
        return {"error": "Respuesta LLM no era JSON válido", "raw": raw}
    except Exception as e:
        return {"error": str(e)}


def generar_muestra_vocal_prompt(datos_anamnesis: dict) -> dict:
    sintomas = datos_anamnesis.get("sintomas", {})
    motivo = datos_anamnesis.get("motivo_consulta", "")

    instrucciones = []
    if sintomas.get("nodo_cordial") or sintomas.get("disfonia"):
        instrucciones.append("Incluir secuencia /m/-a/-u/ para resonancia")
    if sintomas.get("tension_muscular") or sintomas.get("dolor"):
        instrucciones.append("Incluir Le Huche y descenso laríngeo")
    if sintomas.get("presbifonia"):
        instrucciones.append("Incluir glissandos y vocalizaciones proyectadas")
    if not instrucciones:
        instrucciones = [
            "Iniciar con respiración abdominal 1 min",
            "Secuencia /m/-a/-u/ 5 veces",
            "Glissandos cortos en rango cómodo 5 veces",
            "Leer 3 frases balanceadas",
        ]

    return {
        "instrucciones_grabacion": instrucciones[:5],
        "duracion_estimada_s": 60,
        "orden": [
            {"paso": i + 1, "texto": inst}
            for i, inst in enumerate(instrucciones[:5])
        ],
    }
