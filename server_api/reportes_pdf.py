from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import os
from datetime import datetime


def _nivel_severidad(valor, umbrales):
    if valor is None:
        return ("—", colors.HexColor('#94a3b8'), "N/D")
    if valor <= umbrales[0]:
        return ("0", colors.HexColor('#22c55e'), "Normal")
    elif valor <= umbrales[1]:
        return ("1", colors.HexColor('#eab308'), "Leve")
    elif valor <= umbrales[2]:
        return ("2", colors.HexColor('#f97316'), "Moderado")
    else:
        return ("3", colors.HexColor('#ef4444'), "Marcado")


def _severity_cell(valor, umbrales, unit=""):
    nivel, clr, label = _nivel_severidad(valor, umbrales)
    if valor is None:
        return f'<font color="#94a3b8">N/D</font>'
    hex_clr = clr.hexval() if hasattr(clr, 'hexval') else f"#{clr.red:02x}{clr.green:02x}{clr.blue:02x}" if hasattr(clr, 'red') else '#334155'
    try:
        hex_clr = f"#{int(clr.red*255):02x}{int(clr.green*255):02x}{int(clr.blue*255):02x}"
    except Exception:
        hex_clr = '#334155'
    return f'<font color="{hex_clr}"><b>{nivel}</b></font> {valor}{unit} <font color="#64748b">({label})</font>'


def generar_pdf_clinico(paciente: dict, metricas: dict, img_path: str, pdf_path: str):
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#0f172a'), spaceAfter=4)
    subtitle_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748b'), spaceAfter=10)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#0f172a'), spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#334155'), spaceAfter=4, leading=12)
    disclaimer_style = ParagraphStyle('DisclaimerStyle', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#64748b'), spaceAfter=3, leading=10, borderColor=colors.HexColor('#e2e8f0'), borderWidth=0.5, borderPadding=4)

    elements = []

    elements.append(Paragraph("VocalisLab — Reporte Bioacústico Vocal", title_style))
    elements.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"Motor: Praat/Parselmouth {metricas.get('parselmouth_version', 'N/D')} | "
        f"Script: {metricas.get('praat_script', 'N/D')}",
        subtitle_style
    ))

    audio = metricas.get("audio", {})
    grbas_str = paciente.get("grbas", "G0 R0 B0 A0 S0")
    rasati_str = paciente.get("rasati", "R0 A0 S0 A20 T0 I0")

    info_data = [
        [Paragraph(f"<b>Paciente:</b> {paciente.get('nombre', 'N/A')}", body_style),
         Paragraph(f"<b>DNI:</b> {paciente.get('dni', 'N/A')}", body_style)],
        [Paragraph(f"<b>Edad:</b> {paciente.get('edad', 'N/A')} años | <b>Sexo:</b> {paciente.get('sexo', 'N/A')}", body_style),
         Paragraph(f"<b>TMF:</b> {paciente.get('tmf', '0')} s", body_style)],
        [Paragraph(f"<b>GRBAS:</b> {grbas_str}", body_style),
         Paragraph(f"<b>RASATI:</b> {rasati_str}", body_style)],
        [Paragraph(f"<b>Motivo:</b> {paciente.get('motivo', 'N/A')}", body_style),
         Paragraph(f"<b>Derivador:</b> {paciente.get('derivador', 'N/A')}", body_style)],
        [Paragraph(f"<b>Audio:</b> SR={audio.get('sample_rate_hz', 'N/D')} Hz, Dur={audio.get('duration_s', 'N/D')}s, RMS={audio.get('rms', 'N/D')}", body_style),
         Paragraph(f"<b>Hash:</b> {audio.get('file_hash_sha256', 'N/D')[:16]}...", body_style)],
    ]
    t = Table(info_data, colWidths=[270, 270])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))

    if not audio.get("valid", True):
        issues_text = " | ".join(audio.get("issues", []))
        elements.append(Paragraph(f'<font color="#ef4444"><b>ALERTA DE CALIDAD DE AUDIO:</b></font> {issues_text}', disclaimer_style))
        elements.append(Spacer(1, 4))

    elements.append(Paragraph("<b>1. Métricas Bioacústicas Principales</b>", section_style))
    metrics_data = [
        ["Parámetro", "Valor", "Severidad", "Referencia"],
        ["F0 media", f"{metricas.get('f0_mean', 'N/D')} Hz",
         _severity_cell(metricas.get('f0_mean'), (0, 0, 0), " Hz"),
         "Variable (edad, sexo)"],
        ["Jitter local", f"{metricas.get('jitter_pct', 'N/D')}%",
         _severity_cell(metricas.get('jitter_pct'), (1.04, 2.0, 3.0), "%"),
         "< 1.04%"],
        ["Shimmer local", f"{metricas.get('shimmer_pct', 'N/D')}%",
         _severity_cell(metricas.get('shimmer_pct'), (3.81, 5.0, 7.0), "%"),
         "< 3.81%"],
        ["Shimmer (dB)", f"{metricas.get('shimmer_db', 'N/D')} dB",
         _severity_cell(metricas.get('shimmer_db'), (0.5, 1.0, 2.0), " dB"),
         "< 0.5 dB"],
        ["HNR", f"{metricas.get('hnr_db', 'N/D')} dB",
         _severity_cell(metricas.get('hnr_db'), (20, 15, 10), " dB"),
         "> 20 dB"],
        ["CPPS", f"{metricas.get('cpps_db', 'N/D')} dB",
         _severity_cell(metricas.get('cpps_db'), (5.5, 3.0, 1.0), " dB"),
         "> 5.5 dB"],
    ]
    t_metrics = Table(metrics_data, colWidths=[100, 95, 145, 140])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("<b>2. AVQI v03.01 — Componentes y resultado</b>", section_style))
    avqi_data = [
        ["Componente AVQI v03.01", "Resultado", "Unidad"],
        ["CPPs (Cepstral Peak Prominence Smoother)", str(metricas.get('cpps_db', 'N/D')), "dB"],
        ["HNR (Harmonics-to-Noise Ratio)", str(metricas.get('hnr_db', 'N/D')), "dB"],
        ["Shimmer local", str(metricas.get('shimmer_pct', 'N/D')), "%"],
        ["Shimmer local (dB)", str(metricas.get('shimmer_db', 'N/D')), "dB"],
        ["Pendiente espectral (Spectral Slope)", str(metricas.get('spectral_slope', 'N/D')), "dB/oct"],
        ["Tilt espectral (Spectral Tilt)", str(metricas.get('spectral_tilt', 'N/D')), "dB"],
        ["AVQI v03.01", str(metricas.get('avqi', 'N/D')) if metricas.get('avqi_calculable') else "NO CALCULABLE", ""],
        ["Versión del script", metricas.get('praat_script', 'N/D'), ""],
        ["Tipo de muestra", "Vocal /a/ sostenida", ""],
    ]
    t_avqi = Table(avqi_data, colWidths=[260, 140, 80])
    avqi_style_list = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#eff6ff')]),
    ]
    if metricas.get('avqi') is not None and metricas.get('avqi_calculable'):
        avqi_nivel, avqi_clr, avqi_label = _nivel_severidad(metricas['avqi'], (2.0, 2.9, 3.5))
        try:
            avqi_hex = f"#{int(avqi_clr.red*255):02x}{int(avqi_clr.green*255):02x}{int(avqi_clr.blue*255):02x}"
        except Exception:
            avqi_hex = '#334155'
        avqi_style_list.append(('BACKGROUND', (1, 8), (1, 8), colors.HexColor(avqi_hex)))
        avqi_style_list.append(('TEXTCOLOR', (1, 8), (1, 8), colors.white))
    elif not metricas.get('avqi_calculable', True):
        avqi_style_list.append(('BACKGROUND', (1, 8), (1, 8), colors.HexColor('#94a3b8')))
        avqi_style_list.append(('TEXTCOLOR', (1, 8), (1, 8), colors.white))
    t_avqi.setStyle(TableStyle(avqi_style_list))
    elements.append(t_avqi)
    elements.append(Spacer(1, 4))

    if metricas.get('avqi_error'):
        elements.append(Paragraph(f'<font color="#f97316"><b>Nota AVQI:</b></font> {metricas["avqi_error"]}', disclaimer_style))

    if not metricas.get('avqi_calculable', True):
        elements.append(Paragraph(
            '<font color="#ef4444"><b>AVQI NO CALCULABLE:</b></font> '
            'No se pudieron extraer los 6 componentes requeridos por AVQI v03.01. '
            'El valor no debe usarse para clasificación clínica.',
            disclaimer_style
        ))
    elif metricas.get('avqi') is not None and metricas['avqi'] == 0.0:
        elements.append(Paragraph(
            '<font color="#ef4444"><b>ALERTA:</b></font> '
            'AVQI = 0.0 es un valor sospechosamente bajo. Verificar calidad del audio y validez del análisis.',
            disclaimer_style
        ))

    elements.append(Spacer(1, 6))
    if os.path.exists(img_path):
        elements.append(PageBreak())
        elements.append(Paragraph("<b>3. Gráficos Clínicos (Praat & VOXplot Profile)</b>", section_style))
        elements.append(Paragraph("Praat Editor (Waveform & Spectrogram with Pitch/Intensity/Formants) | VOXplot Acoustic Quality Profile & Radar Chart", subtitle_style))
        elements.append(RLImage(img_path, width=520, height=620))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            "Los gráficos fueron generados directamente desde los datos bioacústicos de Praat/Parselmouth y el motor VOXplot. "
            "El panel superior incluye la forma de onda con pulsos glóticos y el espectrograma con contornos de Pitch, Intensidad y Formantes. "
            "El panel inferior detalla el perfil VOXplot de 16 parámetros y el radar chart de severidad multifactorial.",
            disclaimer_style
        ))
        elements.append(Spacer(1, 8))

    elements.append(Paragraph("<b>4. Interpretación Asistida por IA</b>", section_style))
    sintesis = paciente.get('sintesis_ia', '')
    if sintesis and sintesis.strip():
        for para in sintesis.split('\n'):
            if para.strip():
                elements.append(Paragraph(para, body_style))
    else:
        elements.append(Paragraph(
            '<font color="#64748b"><i>Síntesis automática no disponible. '
            'Los resultados bioacústicos fueron calculados, pero no se pudo generar la interpretación asistida.</i></font>',
            body_style
        ))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>5. Aviso Clínico Obligatorio</b>", section_style))
    disclaimers = [
        "Este informe es una herramienta de apoyo y no sustituye la evaluación clínica del profesional fonoaudiólogo.",
        "Los valores bioacústicos son mediciones objetivas. La interpretación diagnóstica es responsabilidad exclusiva del clínico.",
        "Los rangos de referencia son orientativos y dependen de edad, sexo, tarea vocal, contexto y población normativa utilizada.",
        "El AVQI v03.01 fue validado para clasificación de disfonía en adultos. Su applicabilidad a niños o poblaciones específicas debe considerarse con cautela.",
        "Los puntos de corte del AVQI varían según versión, idioma y población. Los valores mostrados son referenciales y no universales.",
        "Este sistema no almacena diagnósticos. Todos los resultados son mediciones instrumentales que requieren correlación clínica.",
    ]
    for d in disclaimers:
        elements.append(Paragraph(f"• {d}", disclaimer_style))

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f"<b>Responsable:</b> {paciente.get('derivador', 'N/D')} | "
        f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y')} | "
        f"<b>Hash:</b> {audio.get('file_hash_sha256', 'N/D')}",
        disclaimer_style
    ))

    doc.build(elements)
