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
    advertencias: List[str] = None,
) -> Dict[str, Any]:
    """Extrae un diccionario estandarizado de variables con nombres limpios
    ({{paciente_nombre}}, {{vhi10_score}}, etc.) para inyectar en plantillas de
    Canva, Figma, Placid, Bannerbear o HTML/CSS.
    """
    profesional = profesional or {}
    evaluacion = evaluacion or {}
    
    fecha_hoy = __import__('datetime').datetime.now().strftime("%d/%m/%Y")
    
    # Formatear la lista de ejercitación para la plantilla.
    # Precaución STOP por ejercicio: viene del frontend o se enriquece acá
    # desde las fichas clínicas (bank_id).
    try:
        from recomendar_motor import precauciones_por_bank_id
        _prec_map = precauciones_por_bank_id()
    except Exception:
        _prec_map = {}
    ejercicios_formateados = []
    for idx, ex in enumerate(ejercicios, 1):
        pasos = ex.get("steps", []) or []
        pasos_str = "\n".join([f"{i}. {p}" for i, p in enumerate(pasos, 1)])
        precaucion = (ex.get("precaucion") or "").strip() or _prec_map.get(
            str(ex.get("id", "")).strip().lower(), "")
        ejercicios_formateados.append({
            "numero": idx,
            "id": ex.get("id", ""),
            "nombre": ex.get("name", f"Ejercicio {idx}"),
            "descripcion": ex.get("description", ""),
            "duracion": f"{ex.get('duration_min', 5)} min/día",
            "pasos_lista": pasos,
            "pasos_texto": pasos_str,
            "seccion": ex.get("seccion_id", "general"),
            "precaucion": precaucion,
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

        # Seguridad clínica (STOP imprimible)
        "advertencias": [str(a).strip() for a in (advertencias or []) if str(a).strip()],
    }




# ─── Motor Canva: discontinuado (exigía cuenta Enterprise). Ver git history. ───


# ─── 1. Cliente Figma REST API ──────────────────────────────────

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


# ─── 2. HTML/CSS Headless Engine (motor interno principal) ────────

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
        """Genera el código HTML editorial con CSS vector moderno.

        Layout estricto con tablas (sin floats ni posicionamiento absoluto)
        para que WeasyPrint no solape elementos entre sí ni con el pie.
        """
        import html as _htmlmod
        ejercicios_html = ""
        for ex in variables.get("ejercicios", []):
            pasos_li = "".join(
                [f"<li><span class='checkbox'>☐</span> {_htmlmod.escape(str(p))}</li>"
                 for p in ex.get("pasos_lista", [])])
            prec = (ex.get("precaucion") or "").strip()
            prec_html = (f"<p class='stop'>⚠ STOP — {_htmlmod.escape(prec)}</p>"
                         if prec else "")
            ejercicios_html += f"""
            <div class="exercise-card">
              <table class="card-header"><tr>
                <td class="ex-number">{ex['numero']}</td>
                <td class="ex-title"><h3>{_htmlmod.escape(str(ex['nombre']))}</h3></td>
                <td class="ex-dosis">{_htmlmod.escape(str(ex['duracion']))}</td>
              </tr></table>
              <p class="ex-desc">{_htmlmod.escape(str(ex['descripcion']))}</p>
              {prec_html}
              <ul class="steps-list">
                {pasos_li}
              </ul>
            </div>
            """
        advs = [str(a).strip() for a in variables.get("advertencias", []) if str(a).strip()]
        advertencias_html = ""
        if advs:
            items = "".join(
                [f"<p class='stop'>⚠ STOP — {_htmlmod.escape(a)}</p>" for a in advs])
            advertencias_html = f"<div class='stop-banner'>{items}</div>"

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
    .exercise-card {{ border: 1px solid #cbd5e1; border-left: 5px solid #1a237e; border-radius: 10px; padding: 12px; margin-bottom: 12px; background: #ffffff; }}
    .card-header {{ width: 100%; border-collapse: collapse; border-bottom: 1px solid #f1f5f9; margin-bottom: 8px; }}
    .card-header td {{ vertical-align: middle; padding: 2px 4px; }}
    .ex-number {{ background: #7c4dff; color: #ffffff; width: 26px; height: 26px; border-radius: 50%; font-weight: bold; font-size: 12px; text-align: center; }}
    .ex-title {{ width: 100%; }}
    .ex-title h3 {{ margin: 0; color: #1a237e; font-size: 16px; }}
    .ex-dosis {{ background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; white-space: nowrap; }}
    .ex-desc {{ font-size: 12px; color: #475569; font-style: italic; margin: 0 0 8px 0; }}
    .steps-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
    .steps-list li {{ padding: 4px 0; border-bottom: 1px dashed #f1f5f9; }}
    .checkbox {{ color: #7c4dff; font-weight: bold; margin-right: 6px; }}
    .stop {{ background: #fdecea; border: 1px solid #b71c1c; color: #b71c1c; font-size: 12px; font-weight: bold; border-radius: 6px; padding: 6px 8px; margin: 8px 0; }}
    .stop-banner {{ margin: 12px 0 20px 0; }}
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
  {advertencias_html}

  <div class="exercises-container">
    {ejercicios_html}
  </div>

  <p style="font-size: 10px; color: #94a3b8; margin-top: 24px;">
    Uso exclusivo en terapia fonoaudiológica supervisada.
  </p>
</body>
</html>"""
        return html_doc
