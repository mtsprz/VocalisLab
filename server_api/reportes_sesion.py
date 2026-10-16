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
              "F0 calculada sobre la voz del paciente (en el dispositivo sobre PCM, o con "
              "Praat en el servidor para audios importados o corregidos).")

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


def _grafico_evolucion(serie: list, ref_min, ref_max, out_png: str, prom=None) -> bool:
    """F0 mediana y media por sesión sobre la banda de referencia."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pts = [p for p in serie if p.get("f0_median_hz")]
        if not pts:
            return False
        xs = list(range(1, len(pts) + 1))
        etiquetas = [f"{i}\n{(p.get('fecha') or '')[5:]}" for i, p in zip(xs, pts)]
        fig, ax = plt.subplots(figsize=(7.5, 3.3))
        if ref_min and ref_max:
            ax.axhspan(float(ref_min), float(ref_max), color="#E0F2FE", alpha=0.9,
                       label=f"Referencia {ref_min}–{ref_max} Hz")
        if prom and prom[0]:
            ax.axhline(float(prom[0]), color="#0284C7", linestyle=":", linewidth=1,
                       label="Promedio esperado")
        ax.plot(xs, [p["f0_median_hz"] for p in pts], marker="o", color="#0284C7",
                linewidth=2, label="F0 mediana")
        medias = [p.get("f0_mean_hz") for p in pts]
        if any(medias):
            ax.plot(xs, medias, marker="s", color="#94A3B8", linewidth=1, label="F0 media")
        ax.axhline(pts[0]["f0_median_hz"], color="#0F172A", linestyle="--", linewidth=0.8,
                   label="Línea de base")
        ax.set_xticks(xs)
        ax.set_xticklabels(etiquetas, fontsize=7)
        ax.set_ylabel("F0 (Hz)")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=7, loc="best")
        fig.tight_layout()
        fig.savefig(out_png, dpi=150)
        plt.close(fig)
        return True
    except Exception:
        return False


def _grafico_vhi(serie: list, out_png: str) -> bool:
    """VHI total por sesión (barras apiladas Funcional/Física/Emocional)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pares = [(i, p) for i, p in enumerate(serie, 1) if p.get("vhi_total") is not None]
        if not pares:
            return False
        xs = [i for i, _ in pares]   # mismo n.º de sesión que la tabla
        pts = [p for _, p in pares]
        f = [p.get("vhi_f") or 0 for p in pts]
        fi = [p.get("vhi_p") or 0 for p in pts]
        e = [p.get("vhi_e") or 0 for p in pts]
        fig, ax = plt.subplots(figsize=(7.5, 2.6))
        ax.bar(xs, f, color="#0284C7", label="Funcional")
        ax.bar(xs, fi, bottom=f, color="#38BDF8", label="Física")
        ax.bar(xs, e, bottom=[a + b for a, b in zip(f, fi)], color="#0F172A", label="Emocional")
        for x, p in zip(xs, pts):
            ax.text(x, p["vhi_total"] + 1, str(p["vhi_total"]), ha="center", fontsize=8)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{x}\n{(p.get('fecha') or '')[5:]}" for x, p in zip(xs, pts)], fontsize=7)
        ax.set_ylabel("VHI (puntos)")
        ax.set_ylim(0, max(p["vhi_total"] for p in pts) * 1.35 + 5)
        ax.set_xlim(0.4, len(serie) + 0.6)
        ax.legend(fontsize=7, ncol=3)
        fig.tight_layout()
        fig.savefig(out_png, dpi=150)
        plt.close(fig)
        return True
    except Exception:
        return False


def _vs_ref(f0, rmin, rmax) -> str:
    import math
    try:
        f0, rmin, rmax = float(f0), float(rmin), float(rmax)
    except Exception:
        return "—"
    if f0 < rmin:
        return f"debajo ({12 * math.log2(f0 / rmin):.1f} st)"
    if f0 > rmax:
        return f"encima (+{12 * math.log2(f0 / rmax):.1f} st)"
    return "dentro"


def generar_pdf_evolucion(datos: dict, firma: dict = None, out_path: str = "") -> str:
    """datos: {paciente, edad, sexo, referencia:{min_hz, max_hz, promedio_min_hz,
    promedio_max_hz, fuente}, serie:[{fecha, tipo, f0_median_hz, f0_mean_hz,
    f0_p5_hz, f0_p95_hz, f0_sd_semitones, metodo, vhi_total, vhi_f, vhi_p, vhi_e,
    vhi_instrumento, resumen, indicaciones}]}."""
    import math
    f = firma_profesional(firma)
    out_path = out_path or tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    st = _styles()
    d = datos or {}
    ref = d.get("referencia") or {}
    serie = d.get("serie") or []
    rmin, rmax = ref.get("min_hz"), ref.get("max_hz")
    story = [
        Paragraph("Informe de evolución — Voz", st["RsTitle"]),
        Paragraph(escape(_firma_linea(f)), st["RsSmall"]),
        HRFlowable(width="100%", color=ACERO, thickness=1),
        Spacer(1, 4 * mm),
    ]
    prom = ""
    if ref.get("promedio_min_hz"):
        a, b = ref["promedio_min_hz"], ref.get("promedio_max_hz") or ref["promedio_min_hz"]
        prom = f" · promedio esperado {a if a == b else f'{a}–{b}'} Hz"
    story.append(_tabla_datos([
        # Celdas de texto plano (no Paragraph): sin escape, si no se ve "&amp;".
        ["Paciente:", str(d.get("paciente", "—"))],
        ["Sexo / edad:", f"{d.get('sexo') or '—'} · {d.get('edad') if d.get('edad') is not None else '—'} años"],
        ["Referencia F0:", f"{rmin or '—'}–{rmax or '—'} Hz{prom}" + (f" ({ref['fuente']})" if ref.get("fuente") else "")],
        ["Sesiones:", f"{len(serie)} · {serie[0].get('fecha', '') if serie else ''} a {serie[-1].get('fecha', '') if serie else ''}"],
    ], [38 * mm, 132 * mm]))

    # Cambio entre la primera y la última sesión con dato
    con_f0 = [p for p in serie if p.get("f0_median_hz")]
    con_vhi = [p for p in serie if p.get("vhi_total") is not None]
    cambios = []
    if len(con_f0) >= 2:
        a, b = float(con_f0[0]["f0_median_hz"]), float(con_f0[-1]["f0_median_hz"])
        cambios.append(f"F0 mediana en el habla: {a:.1f} → {b:.1f} Hz ({12 * math.log2(b / a):+.1f} semitonos); "
                       f"última sesión {_vs_ref(b, rmin, rmax)} de la referencia.")
    elif con_f0:
        b = float(con_f0[-1]["f0_median_hz"])
        cambios.append(f"F0 mediana en el habla: {b:.1f} Hz, {_vs_ref(b, rmin, rmax)} de la referencia.")
    if len(con_vhi) >= 2:
        cambios.append(f"VHI: {con_vhi[0]['vhi_total']} → {con_vhi[-1]['vhi_total']} puntos "
                       f"({con_vhi[-1]['vhi_total'] - con_vhi[0]['vhi_total']:+d}).")
    elif con_vhi:
        cambios.append(f"VHI ({con_vhi[-1].get('vhi_instrumento') or 'VHI'}): {con_vhi[-1]['vhi_total']} puntos "
                       f"(funcional {con_vhi[-1].get('vhi_f')}, física {con_vhi[-1].get('vhi_p')}, "
                       f"emocional {con_vhi[-1].get('vhi_e')}).")
    if cambios:
        story.append(Paragraph("<b>Síntesis</b>", st["RsH2"]))
        for c in cambios:
            story.append(Paragraph("• " + escape(c), st["RsBody"]))

    png = out_path + ".png"
    png2 = out_path + ".vhi.png"
    pr = (ref.get("promedio_min_hz"), ref.get("promedio_max_hz"))
    if serie and _grafico_evolucion(serie, rmin, rmax, png, pr):
        story.append(Paragraph("<b>Altura tonal en el habla espontánea</b>", st["RsH2"]))
        story.append(RLImage(png, width=170 * mm, height=75 * mm))
    if serie and _grafico_vhi(serie, png2):
        story.append(Paragraph("<b>Índice de Incapacidad Vocal (VHI)</b>", st["RsH2"]))
        story.append(RLImage(png2, width=170 * mm, height=59 * mm))

    story.append(Paragraph("<b>Serie por sesión</b>", st["RsH2"]))
    rows = [["N.º", "Fecha", "Tipo", "F0 med", "F0 media", "p5–p95", "SD st", "vs ref.", "VHI"]]
    for i, p in enumerate(serie, 1):
        vhi = "—"
        if p.get("vhi_total") is not None:
            vhi = f"{p['vhi_total']} ({p.get('vhi_f', 0)}/{p.get('vhi_p', 0)}/{p.get('vhi_e', 0)})"
        rows.append([str(i), str(p.get("fecha") or "—"), str(p.get("tipo") or "—")[:16],
                     _fmt(p.get("f0_median_hz")), _fmt(p.get("f0_mean_hz")),
                     f"{_fmt(p.get('f0_p5_hz'), 0)}–{_fmt(p.get('f0_p95_hz'), 0)}",
                     _fmt(p.get("f0_sd_semitones"), 2),
                     _vs_ref(p.get("f0_median_hz"), rmin, rmax) if p.get("f0_median_hz") else "—", vhi])
    t = Table(rows, colWidths=[9 * mm, 20 * mm, 26 * mm, 15 * mm, 16 * mm, 20 * mm, 13 * mm, 24 * mm, 27 * mm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Paragraph("VHI entre paréntesis: funcional / física / emocional. "
                           "F0 en Hz medida solo en la voz del paciente.", st["RsSmall"]))

    resumenes = [p for p in serie if p.get("resumen")]
    if resumenes:
        story.append(Paragraph("<b>Síntesis de cada sesión</b>", st["RsH2"]))
        for i, p in enumerate(serie, 1):
            if not p.get("resumen"):
                continue
            txt = f"<b>Sesión {i} · {escape(str(p.get('fecha') or ''))}</b> — {escape(str(p['resumen']))}"
            if p.get("indicaciones"):
                txt += "<br/><i>Indicaciones:</i> " + escape("; ".join(p["indicaciones"]))
            story.append(Paragraph(txt, st["RsBody"]))
        story.append(Paragraph("Síntesis redactadas por IA desde la transcripción y revisadas por el profesional.",
                               st["RsSmall"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"<i>{escape(ACLARACION)}</i>", st["RsSmall"]))
    story.append(Paragraph(escape(_firma_linea(f)), st["RsFirma"]))
    _doc(out_path, "Informe de evolución — Voz").build(story)
    for x in (png, png2):
        try:
            if os.path.exists(x):
                os.unlink(x)
        except Exception:
            pass
    return out_path
