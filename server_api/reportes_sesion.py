"""VocalisLab — Informes PDF de sesión y de evolución (Vocalis Companion).

ReportLab, paleta clínica (Navy #0F172A + Acero #0284C7 + STOP #991B1B).
Firma configurable por PROFESIONAL_NOMBRE / PROFESIONAL_MATRICULA.
Prohibido: la leyenda "especialista en voz" no aparece en estos informes.
"""
import os
import tempfile
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, HRFlowable, Image as RLImage)

NAVY = HexColor("#0F172A")
ACERO = HexColor("#0284C7")
INK = HexColor("#1E293B")
GRIS = HexColor("#64748B")
BORDE = HexColor("#E2E8F0")
FONDO = HexColor("#F8FAFC")
ROJO = HexColor("#991B1B")
ROJO_BG = HexColor("#FEF2F2")

ACLARACION = ("Valores de referencia orientativos: requieren criterio clínico. "
              "Las métricas oficiales son las calculadas en el dispositivo sobre PCM.")

TASK_LABEL = {
    "vocal_sostenida_a": "Vocal sostenida /a/",
    "conteo": "Conteo",
    "lectura": "Lectura",
    "conversacion_espontanea": "Conversación espontánea",
}


def firma_profesional(firma: dict = None) -> dict:
    f = firma if isinstance(firma, dict) else {}
    return {
        "nombre": (f.get("nombre") or os.environ.get("PROFESIONAL_NOMBRE", "Matías Perez")).strip(),
        "titulo": (f.get("titulo") or "Fonoaudiólogo").strip(),
        "matricula": (f.get("matricula") or os.environ.get("PROFESIONAL_MATRICULA", "M.P. 7276")).strip(),
    }


def _firma_linea(f: dict) -> str:
    return f"{f['nombre']} – {f['titulo']} – {f['matricula']}"


def _styles():
    s = getSampleStyleSheet()

    def _add(name, **kw):
        if name not in s:
            s.add(ParagraphStyle(name, **kw))
    _add("RsTitle", parent=s["Title"], fontSize=22, textColor=NAVY, spaceAfter=2 * mm)
    _add("RsH2", parent=s["Heading2"], fontSize=14, textColor=NAVY,
         spaceBefore=6 * mm, spaceAfter=2 * mm)
    _add("RsBody", parent=s["Normal"], fontSize=11, textColor=INK, leading=15,
         spaceAfter=2 * mm)
    _add("RsSmall", parent=s["Normal"], fontSize=9, textColor=GRIS, leading=12)
    _add("RsFirma", parent=s["Normal"], fontSize=11, textColor=NAVY,
         alignment=TA_CENTER, spaceBefore=8 * mm)
    return s


def _doc(out_path: str, titulo: str):
    return SimpleDocTemplate(out_path, pagesize=A4, topMargin=18 * mm,
                             bottomMargin=20 * mm, leftMargin=16 * mm,
                             rightMargin=16 * mm, title=titulo)


def _tabla_datos(rows, anchos):
    t = Table(rows, colWidths=anchos)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDE),
    ]))
    return t


def _fmt(v, nd=1, suf=""):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{nd}f}{suf}"
    except Exception:
        return "—"


def generar_pdf_sesion(datos: dict, firma: dict = None, out_path: str = "") -> str:
    """datos: {paciente, fecha, duracion_sec, codec, bitrate_kbps, dsp_version,
    referencia:{sexo, edad, min_hz, max_hz}, metricas:[{task_type, f0_median_hz,
    f0_sd_semitones, intensity_mean_db, jitter_pct, shimmer_pct, hnr_db,
    mpt_sec, validada}]}."""
    f = firma_profesional(firma)
    out_path = out_path or tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    st = _styles()
    story = [
        Paragraph("Informe de sesión — Voz", st["RsTitle"]),
        Paragraph(escape(_firma_linea(f)), st["RsSmall"]),
        HRFlowable(width="100%", color=ACERO, thickness=1),
        Spacer(1, 4 * mm),
    ]
    d = datos or {}
    ref = d.get("referencia") or {}
    story.append(_tabla_datos([
        ["Paciente:", escape(str(d.get("paciente", "—")))],
        ["Fecha:", escape(str(d.get("fecha", "—")))],
        ["Duración:", escape(str(d.get("duracion_sec", "—"))) + " s"],
        ["Registro:", escape(f"{d.get('codec', '—')} {d.get('bitrate_kbps', '—')} kbps · {d.get('dsp_version', '')}".strip())],
        ["Referencia:", escape(f"{ref.get('sexo', '—')} · {ref.get('edad', '—')} años · {ref.get('min_hz', '—')}–{ref.get('max_hz', '—')} Hz")],
    ], [42 * mm, 128 * mm]))
    story.append(Paragraph("<b>Métricas por tarea</b>", st["RsH2"]))
    head = ["Tarea", "F0 med (Hz)", "SD (st)", "dB", "Jit %", "Shim %", "HNR", "MPT (s)"]
    rows = [head]
    for m in (d.get("metricas") or []):
        rows.append([
            TASK_LABEL.get(m.get("task_type"), m.get("task_type", "—")),
            _fmt(m.get("f0_median_hz")), _fmt(m.get("f0_sd_semitones"), 2),
            _fmt(m.get("intensity_mean_db")), _fmt(m.get("jitter_pct"), 2),
            _fmt(m.get("shimmer_pct"), 2), _fmt(m.get("hnr_db")),
            _fmt(m.get("mpt_sec")),
        ])
    t = Table(rows, colWidths=[52 * mm] + [18 * mm] * 7, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"<i>{escape(ACLARACION)}</i>", st["RsSmall"]))
    story.append(Paragraph(escape(_firma_linea(f)), st["RsFirma"]))
    _doc(out_path, "Informe de sesión — Voz").build(story)
    return out_path


def _grafico_evolucion(serie: list, ref_min, ref_max, out_png: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        xs = [p.get("n", i + 1) for i, p in enumerate(serie)]
        ys = [p.get("f0_median_hz") for p in serie]
        fig, ax = plt.subplots(figsize=(7.5, 3.2))
        if ref_min and ref_max:
            ax.axhspan(ref_min, ref_max, color="#E0F2FE", alpha=0.9, label="Referencia")
        ax.plot(xs, ys, marker="o", color="#0284C7", linewidth=2)
        if ys and ys[0] is not None:
            ax.axhline(ys[0], color="#0F172A", linestyle="--", linewidth=1, label="Línea de base")
        ax.set_xlabel("Sesión n.º")
        ax.set_ylabel("F0 mediana (Hz)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_png, dpi=150)
        plt.close(fig)
        return True
    except Exception:
        return False


def generar_pdf_evolucion(datos: dict, firma: dict = None, out_path: str = "") -> str:
    """datos: {paciente, referencia:{...}, serie:[{n, fecha, f0_median_hz,
    f0_sd_semitones, intensity_mean_db, jitter_pct, shimmer_pct, hnr_db, mpt_sec}]}."""
    f = firma_profesional(firma)
    out_path = out_path or tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    st = _styles()
    d = datos or {}
    ref = d.get("referencia") or {}
    serie = d.get("serie") or []
    story = [
        Paragraph("Informe de evolución — Voz", st["RsTitle"]),
        Paragraph(escape(_firma_linea(f)), st["RsSmall"]),
        HRFlowable(width="100%", color=ACERO, thickness=1),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>Paciente:</b> {escape(str(d.get('paciente', '—')))} &nbsp;·&nbsp; "
                  f"<b>Referencia:</b> {escape(str(ref.get('sexo', '—')))} · "
                  f"{escape(str(ref.get('edad', '—')))} años · "
                  f"{escape(str(ref.get('min_hz', '—')))}–{escape(str(ref.get('max_hz', '—')))} Hz",
                  st["RsBody"]),
    ]
    png = out_path + ".png"
    if serie and _grafico_evolucion(serie, ref.get("min_hz"), ref.get("max_hz"), png):
        try:
            img = RLImage(png, width=170 * mm, height=73 * mm)
            story.append(img)
            story.append(Spacer(1, 3 * mm))
        except Exception:
            pass
    story.append(Paragraph("<b>Serie por sesión</b>", st["RsH2"]))
    head = ["N.º", "Fecha", "F0 med", "SD st", "dB", "Jit %", "Shim %", "HNR", "MPT"]
    rows = [head]
    for p in serie:
        rows.append([str(p.get("n", "—")), str(p.get("fecha", "—") or "—"),
                     _fmt(p.get("f0_median_hz")), _fmt(p.get("f0_sd_semitones"), 2),
                     _fmt(p.get("intensity_mean_db")), _fmt(p.get("jitter_pct"), 2),
                     _fmt(p.get("shimmer_pct"), 2), _fmt(p.get("hnr_db")),
                     _fmt(p.get("mpt_sec"))])
    t = Table(rows, colWidths=[14 * mm, 30 * mm] + [18 * mm] * 7, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"<i>{escape(ACLARACION)}</i>", st["RsSmall"]))
    story.append(Paragraph(escape(_firma_linea(f)), st["RsFirma"]))
    _doc(out_path, "Informe de evolución — Voz").build(story)
    try:
        if os.path.exists(png):
            os.unlink(png)
    except Exception:
        pass
    return out_path
