"""VocalisLab Pro — Motor de Integración de Plantillas Editoriales (Figma, Canva y HTML Headless).

Separa la lógica clínica de la maquetación gráfica para lograr cuadernillos de nivel
editorial 100% vectoriales, sin depender de inconsistencias de IA en tiempo de ejecución.

Arquitectura:
  [ Lógica Clínica / Supabase ] ──► [ Motor de Plantillas ] ──► [ Canva API / Figma REST / HTML Headless ]
                                                                       │
  [ PDF Final Editorial ] ◄────────────────────────────────────────────┘
"""

import os
import json
import httpx
import traceback
from typing import Optional, Dict, Any, List

# ─── Dict Extractor de Variables Clínicas (Edición 2026) ─────────────

def extraer_variables_cuadernillo(
    paciente_nombre: str,
    titulo: str,
    sesiones: int,
    ejercicios: List[Dict[str, Any]],
    contrato: Dict[str, Any],
    notas: str = "",
    profesional: Dict[str, Any] = None,
    evaluacion: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Extrae un diccionario estandarizado de variables con nombres limpios
    ({{paciente_nombre}}, {{vhi10_score}}, etc.) para inyectar en plantillas de
    Canva, Figma, Placid, Bannerbear o HTML/CSS.
    """
    profesional = profesional or {}
    evaluacion = evaluacion or {}
    
    fecha_hoy = __import__('datetime').datetime.now().strftime("%d/%m/%Y")
    
    # Formatear la lista de ejercitación para la plantilla
    ejercicios_formateados = []
    for idx, ex in enumerate(ejercicios, 1):
        pasos = ex.get("steps", []) or []
        pasos_str = "\n".join([f"{i}. {p}" for i, p in enumerate(pasos, 1)])
        ejercicios_formateados.append({
            "numero": idx,
            "id": ex.get("id", ""),
            "nombre": ex.get("name", f"Ejercicio {idx}"),
            "descripcion": ex.get("description", ""),
            "duracion": f"{ex.get('duration_min', 5)} min/día",
            "pasos_lista": pasos,
            "pasos_texto": pasos_str,
            "seccion": ex.get("seccion_id", "general"),
        })

    return {
        # Datos Institucionales
        "profesional_nombre": profesional.get("profesional_nombre", "Lic. Matías Pérez"),
        "profesional_titulo": profesional.get("profesional_titulo", "Fonoaudiólogo · Especialista en Voz"),
        "profesional_matricula": profesional.get("profesional_matricula", "M.P. 7276"),
        "profesional_contacto": f"{profesional.get('profesional_telefono', '')} | {profesional.get('profesional_email', '')}".strip(" |"),
        "firma_institucional": "Matías Pérez · Fonoaudiólogo · M.P. 7276",
        
        # Datos del Tratamiento
        "paciente_nombre": paciente_nombre or "Paciente Sin Especificar",
        "cuadernillo_titulo": titulo or "Cuadernillo Terapéutico Vocal",
        "fecha_creacion": fecha_hoy,
        "cantidad_sesiones": sesiones or 8,
        "frecuencia_sesiones": contrato.get("frecuencia", "2 veces por semana"),
        "duracion_sesion_min": contrato.get("duracion_min", 30),
        "notas_profesional": notas or "Realizar los ejercicios con regularidad y sin forzar.",
        
        # Métrica e Indicadores Clínicos
        "vhi10_score": evaluacion.get("vhi10_score", "N/D"),
        "vhi10_grado": evaluacion.get("vhi10_grado", "Evaluación inicial"),
        "riesgo_total_score": evaluacion.get("riesgo_vocal_score", "N/D"),
        "tme_sostenido_s": evaluacion.get("tme_o", "—"),
        "tme_suave_s": evaluacion.get("tme_s", "—"),
        "indice_so": evaluacion.get("indice_so", "—"),
        
        # Lista de Ejercicios
        "ejercicios_total": len(ejercicios),
        "ejercicios": ejercicios_formateados,
        "ejercicios_json_str": json.dumps(ejercicios_formateados, ensure_ascii=False),
    }


# ─── 1. Cliente Canva Connect API (Autofill) ──────────────────────────

class CanvaConnectEngine:
    """Conector con la API oficial de Canva Connect (Autofill API).
    Completa automáticamente una plantilla máster prediseñada en Canva.
    """
    def __init__(self):
        self.api_key = os.environ.get("CANVA_API_KEY", "").strip()
        self.template_id = os.environ.get("CANVA_TEMPLATE_ID", "").strip()
        self.base_url = "https://api.canva.com/v1"

    def esta_configurado(self) -> bool:
        return bool(self.api_key and self.template_id)

    async def generar_cuadernillo_autofill(self, variables: Dict[str, Any]) -> Optional[str]:
        """Envía el payload de variables a Canva y devuelve la URL del PDF vectorial."""
        if not self.esta_configurado():
            print("[plantillas_engine] Canva Connect no configurado (falta CANVA_API_KEY / CANVA_TEMPLATE_ID)")
            return None
            
        try:
            async with httpx.AsyncClient() as client:
                # 1. Solicitar Autofill Job
                res = await client.post(
                    f"{self.base_url}/autofill",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "brand_template_id": self.template_id,
                        "title": f"Cuadernillo_{variables['paciente_nombre']}",
                        "data": {
                            "paciente_nombre": {"type": "text", "text": variables["paciente_nombre"]},
                            "cuadernillo_titulo": {"type": "text", "text": variables["cuadernillo_titulo"]},
                            "profesional_nombre": {"type": "text", "text": variables["profesional_nombre"]},
                            "profesional_matricula": {"type": "text", "text": variables["profesional_matricula"]},
                            "notas_profesional": {"type": "text", "text": variables["notas_profesional"]},
                        }
                    },
                    timeout=30.0
                )
                if res.status_code not in (200, 201, 202):
                    print(f"[plantillas_engine] Error Canva Autofill {res.status_code}: {res.text[:200]}")
                    return None
                    
                data = res.json()
                job_id = (data.get("job") or {}).get("id") or data.get("id")
                if not job_id:
                    return None
                    
                # 2. Polling del estado de exportación a PDF
                for _ in range(10):
                    import asyncio
                    await asyncio.sleep(2)
                    poll = await client.get(
                        f"{self.base_url}/autofill/{job_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=15.0
                    )
                    if poll.status_code == 200:
                        p_data = poll.json()
                        status = (p_data.get("job") or {}).get("status")
                        if status == "success":
                            pdf_url = ((p_data.get("job") or {}).get("result") or {}).get("pdf_url")
                            return pdf_url
            return None
        except Exception as e:
            print(f"[plantillas_engine] Excepción en Canva Engine: {e}")
            return None


# ─── 2. Cliente Figma REST API / MCP ──────────────────────────────────

class FigmaRESTEngine:
    """Conector con la API REST de Figma para inspección de componentes,
    actualización de nodos vectoriales y exportación en PDF de alta resolución.
    """
    def __init__(self):
        self.access_token = os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()
        self.file_key = os.environ.get("FIGMA_FILE_KEY", "").strip()
        self.base_url = "https://api.figma.com/v1"

    def esta_configurado(self) -> bool:
        return bool(self.access_token and self.file_key)

    async def exportar_frame_pdf(self, node_id: str) -> Optional[str]:
        """Exporta un nodo/frame de Figma a PDF vectorial limpio."""
        if not self.esta_configurado():
            return None
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{self.base_url}/images/{self.file_key}?ids={node_id}&format=pdf",
                    headers={"X-Figma-Token": self.access_token},
                    timeout=30.0
                )
                if res.status_code == 200:
                    images = res.json().get("images") or {}
                    return images.get(node_id)
            return None
        except Exception as e:
            print(f"[plantillas_engine] Error exportando de Figma: {e}")
            return None


# ─── 3. HTML/CSS Headless Engine (Solución Nativa para Docker) ────────

class HTMLTemplateEngine:
    """Generador HTML/CSS/SVG Headless nativo. Convierte plantillas HTML
    diseñadas en Figma/Canva e inyecta las variables clínicas directamente,
    sirviendo como un puente ultrarrápido y sin costo de cuota de API.
    """
    @staticmethod
    def renderizar_html_clinico(variables: Dict[str, Any]) -> str:
        """Genera el código HTML editorial con CSS vector moderno."""
        ejercicios_html = ""
        for ex in variables.get("ejercicios", []):
            pasos_li = "".join([f"<li><span class='checkbox'>☐</span> {p}</li>" for p in ex.get("pasos_lista", [])])
            ejercicios_html += f"""
            <div class="exercise-card">
              <div class="card-header">
                <span class="ex-number">{ex['numero']}</span>
                <h3>{ex['nombre']}</h3>
                <span class="ex-dosis">{ex['duracion']}</span>
              </div>
              <p class="ex-desc">{ex['descripcion']}</p>
              <ul class="steps-list">
                {pasos_li}
              </ul>
            </div>
            """

        html_doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>{variables['cuadernillo_titulo']}</title>
  <style>
    @page {{ size: A4; margin: 15mm; }}
    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1e293b; background: #ffffff; line-height: 1.5; }}
    .header {{ text-align: center; border-bottom: 2px solid #7c4dff; padding-bottom: 12px; margin-bottom: 20px; }}
    .header h1 {{ color: #1a237e; font-size: 24px; margin: 0; }}
    .header p {{ color: #64748b; font-size: 12px; margin: 4px 0 0 0; }}
    .meta-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 20px; font-size: 13px; }}
    .exercise-card {{ border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px; margin-bottom: 16px; background: #ffffff; page-break-inside: avoid; }}
    .card-header {{ display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; margin-bottom: 8px; }}
    .ex-number {{ background: #7c4dff; color: #ffffff; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }}
    .card-header h3 {{ margin: 0; color: #1a237e; font-size: 16px; flex: 1; }}
    .ex-dosis {{ background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
    .ex-desc {{ font-size: 12px; color: #475569; font-style: italic; margin-bottom: 10px; }}
    .steps-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
    .steps-list li {{ padding: 4px 0; border-bottom: 1px dashed #f1f5f9; }}
    .checkbox {{ color: #7c4dff; font-weight: bold; margin-right: 6px; }}
    .footer {{ text-align: center; font-size: 10px; color: #94a3b8; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{variables['cuadernillo_titulo']}</h1>
    <p>{variables['profesional_nombre']} — {variables['profesional_matricula']}</p>
  </div>

  <div class="meta-box">
    <strong>Paciente:</strong> {variables['paciente_nombre']} &nbsp;|&nbsp; 
    <strong>Fecha:</strong> {variables['fecha_creacion']} &nbsp;|&nbsp; 
    <strong>Sesiones recomendadas:</strong> {variables['cantidad_sesiones']}
  </div>

  <div class="exercises-container">
    {ejercicios_html}
  </div>

  <div class="footer">
    {variables['firma_institucional']} · Uso exclusivo en terapia fonoaudiológica supervisada.
  </div>
</body>
</html>"""
        return html_doc
