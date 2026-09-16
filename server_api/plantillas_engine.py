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
    """Conector con la API oficial de Canva Connect (Autofill + Export).

    Auth: OAuth 2.0 con PKCE — el access token del usuario se obtiene en
    /api/canva/auth/url y se guarda en Supabase (canva_tokens). Aquí solo
    se usa el token vigente (con refresh automático).

    Flujo: POST /rest/v1/autofills → poll → design_id →
           POST /rest/v1/exports {format pdf} → poll → urls[0].
    """
    def __init__(self):
        self.template_id = os.environ.get("CANVA_TEMPLATE_ID", "").strip()
        self.base_url = "https://api.canva.com/rest/v1"

    def esta_configurado(self) -> bool:
        """Credenciales OAuth + template presentes en el servidor."""
        from canva_auth import credenciales_presentes
        return bool(credenciales_presentes() and self.template_id)

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _poll_job(self, client, path: str, token: str,
                        intentos: int = 24, espera: float = 5.0) -> Optional[dict]:
        import asyncio
        for _ in range(intentos):
            await asyncio.sleep(espera)
            try:
                poll = await client.get(f"{self.base_url}{path}",
                                        headers=self._headers(token), timeout=20.0)
            except Exception as e:
                print(f"[plantillas_engine] Poll Canva {path}: {e}")
                continue
            if poll.status_code != 200:
                print(f"[plantillas_engine] Poll Canva {path} {poll.status_code}: {poll.text[:200]}")
                continue
            job = (poll.json().get("job") or {})
            status = job.get("status")
            if status == "success":
                return job
            if status == "failed":
                print(f"[plantillas_engine] Job Canva fallido {path}: {str(job.get('error'))[:300]}")
                return None
        print(f"[plantillas_engine] Timeout esperando job Canva {path}")
        return None

    def _texto(self, v: Any) -> dict:
        return {"type": "text", "text": str(v or "")[:10000]}

    async def generar_cuadernillo_autofill(self, variables: Dict[str, Any]) -> Optional[str]:
        """Autofill del brand template + exportación a PDF. Devuelve la URL del PDF."""
        if not self.esta_configurado():
            print("[plantillas_engine] Canva: faltan CANVA_CLIENT_ID/SECRET o CANVA_TEMPLATE_ID")
            return None
        try:
            from canva_auth import get_valid_access_token
            token = get_valid_access_token()
        except Exception as e:
            print(f"[plantillas_engine] Canva sin token OAuth: {e}")
            return None

        try:
            async with httpx.AsyncClient() as client:
                # 1. Autofill job desde el brand template
                data_fields = {
                    "paciente_nombre": self._texto(variables.get("paciente_nombre")),
                    "cuadernillo_titulo": self._texto(variables.get("cuadernillo_titulo")),
                    "profesional_nombre": self._texto(variables.get("profesional_nombre")),
                    "profesional_matricula": self._texto(variables.get("profesional_matricula")),
                    "profesional_contacto": self._texto(variables.get("profesional_contacto")),
                    "fecha_creacion": self._texto(variables.get("fecha_creacion")),
                    "cantidad_sesiones": self._texto(variables.get("cantidad_sesiones")),
                    "notas_profesional": self._texto(variables.get("notas_profesional")),
                    "vhi10_score": self._texto(variables.get("vhi10_score")),
                    "riesgo_total_score": self._texto(variables.get("riesgo_total_score")),
                }
                res = await client.post(
                    f"{self.base_url}/autofills",
                    headers=self._headers(token),
                    json={
                        "brand_template_id": self.template_id,
                        "title": f"Cuadernillo_{variables.get('paciente_nombre', 'Paciente')}"[:255],
                        "data": data_fields,
                    },
                    timeout=30.0,
                )
                if res.status_code not in (200, 201, 202):
                    print(f"[plantillas_engine] Error Canva Autofill {res.status_code}: {res.text[:300]}")
                    return None
                job_id = (res.json().get("job") or {}).get("id")
                if not job_id:
                    return None

                # 2. Esperar el diseño autofilled
                job = await self._poll_job(client, f"/autofills/{job_id}", token)
                if not job:
                    return None
                designs = ((job.get("result") or {}).get("designs") or [])
                if not designs or not designs[0].get("id"):
                    print(f"[plantillas_engine] Autofill sin designs: {str(job)[:300]}")
                    return None
                design_id = designs[0]["id"]

                # 3. Exportar el diseño a PDF
                exp = await client.post(
                    f"{self.base_url}/exports",
                    headers=self._headers(token),
                    json={"design_id": design_id, "format": {"type": "pdf"}},
                    timeout=30.0,
                )
                if exp.status_code not in (200, 201, 202):
                    print(f"[plantillas_engine] Error Canva Export {exp.status_code}: {exp.text[:300]}")
                    return None
                exp_id = (exp.json().get("job") or {}).get("id")
                if not exp_id:
                    return None
                exp_job = await self._poll_job(client, f"/exports/{exp_id}", token)
                if not exp_job:
                    return None
                urls = ((exp_job.get("result") or {}).get("urls") or [])
                return urls[0] if urls else None
        except Exception as e:
            print(f"[plantillas_engine] Excepción en Canva Engine: {e}")
            traceback.print_exc()
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

def html_a_pdf_bytes(html_code: str) -> Optional[bytes]:
    """Compila HTML editorial a PDF vectorial con WeasyPrint (open-source,
    100% server-side, sin cuotas ni APIs externas). Devuelve bytes o None."""
    try:
        from weasyprint import HTML
        return HTML(string=html_code).write_pdf()
    except Exception as e:
        print(f"[plantillas_engine] WeasyPrint no disponible o falló: {e}")
        return None


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
                <span class="ex-dosis">{ex['duracion']}</span>
                <h3>{ex['nombre']}</h3>
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
    @page {{ size: A4; margin: 15mm 15mm 24mm 15mm;
      @bottom-center {{ content: "{variables['firma_institucional']} · Página " counter(page) " de " counter(pages);
        font-size: 9px; color: #94a3b8; font-family: Helvetica, Arial, sans-serif; }} }}
    body {{ font-family: Helvetica, Arial, sans-serif; color: #1e293b; background: #ffffff; line-height: 1.5; font-size: 13px; }}
    .header {{ text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 12px; margin-bottom: 6px; }}
    .header h1 {{ color: #1a237e; font-size: 24px; margin: 0; }}
    .header .sub {{ color: #7c4dff; font-size: 13px; font-weight: bold; margin: 4px 0 0 0; }}
    .header p {{ color: #64748b; font-size: 11px; margin: 2px 0 0 0; }}
    .contract {{ background: #f5f3ff; border-left: 4px solid #7c4dff; padding: 10px 12px; margin: 12px 0 20px 0; font-size: 12px; }}
    .exercise-card {{ border: 1px solid #cbd5e1; border-left: 5px solid #1a237e; border-radius: 10px; padding: 14px; margin-bottom: 16px; background: #ffffff; page-break-inside: avoid; }}
    .card-header {{ border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; margin-bottom: 8px; }}
    .ex-number {{ background: #7c4dff; color: #ffffff; width: 24px; height: 24px; border-radius: 50%; font-weight: bold; font-size: 12px; text-align: center; line-height: 24px; float: left; margin-right: 10px; }}
    .card-header h3 {{ margin: 0 0 0 34px; color: #1a237e; font-size: 16px; }}
    .ex-dosis {{ background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; float: right; }}
    .ex-desc {{ font-size: 12px; color: #475569; font-style: italic; margin-bottom: 10px; clear: both; }}
    .steps-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
    .steps-list li {{ padding: 4px 0; border-bottom: 1px dashed #f1f5f9; }}
    .checkbox {{ color: #7c4dff; font-weight: bold; margin-right: 6px; }}
    .footer {{ text-align: center; font-size: 10px; color: #94a3b8; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Consultorio de Voz</h1>
    <p class="sub">Lic. Matías Pérez — Fonoaudiólogo · M.P. 7276</p>
    <p>Manual de Entrenamiento y Rehabilitación Vocal · Edición 2026</p>
    <h1 style="font-size: 19px; margin-top: 8px;">{variables['cuadernillo_titulo']}</h1>
    <p>{variables['profesional_nombre']} — {variables['profesional_matricula']}</p>
  </div>

  <div class="meta-box">
    <strong>Paciente:</strong> {variables['paciente_nombre']} &nbsp;|&nbsp;
    <strong>Fecha:</strong> {variables['fecha_creacion']} &nbsp;|&nbsp;
    <strong>Sesiones recomendadas:</strong> {variables['cantidad_sesiones']}
  </div>

  <div class="contract">
    <strong>Contrato terapéutico:</strong> frecuencia {variables['frecuencia_sesiones']} ·
    sesiones de {variables['duracion_sesion_min']} min. {variables['notas_profesional']}
  </div>

  <div class="exercises-container">
    {ejercicios_html}
  </div>

  <p style="font-size: 10px; color: #94a3b8; margin-top: 24px;">
    Uso exclusivo en terapia fonoaudiológica supervisada.
  </p>
</body>
</html>"""
        return html_doc
