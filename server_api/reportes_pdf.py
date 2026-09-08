import os
import base64
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


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
    try:
        hex_clr = f"#{int(clr.red*255):02x}{int(clr.green*255):02x}{int(clr.blue*255):02x}"
    except Exception:
        hex_clr = '#334155'
    return f'<font color="{hex_clr}"><b>{nivel}</b></font> {valor}{unit} <font color="#64748b">({label})</font>'


def _chart_from_b64(charts, key):
    if not charts:
        return None
    chart_data = charts.get(key, "")
    if chart_data and "base64," in chart_data:
        b64_str = chart_data.split("base64,")[1]
        return base64.b64decode(b64_str)
    return None


def generar_pdf_clinico(paciente: dict, metricas: dict, img_path: str, pdf_path: str, charts: dict = None, cross_check: dict = None):
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor('#0f172a'), spaceAfter=4, alignment=1)
    subtitle_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748b'), spaceAfter=10, alignment=1)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#0f172a'), spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#334155'), spaceAfter=4, leading=12)
    small_style = ParagraphStyle('SmallStyle', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#334155'), spaceAfter=3, leading=10)
    disclaimer_style = ParagraphStyle('DisclaimerStyle', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#64748b'), spaceAfter=3, leading=10, borderColor=colors.HexColor('#e2e8f0'), borderWidth=0.5, borderPadding=4)
    note_style = ParagraphStyle('NoteStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#334155'), spaceAfter=6, leading=14, borderWidth=0.5, borderColor=colors.HexColor('#cbd5e1'), borderPadding=8)

    elements = []
    audio = metricas.get("audio", {})
    prof_name = paciente.get("profesional_nombre", "")
    prof_title = paciente.get("profesional_titulo", "")
    prof_mat = paciente.get("profesional_matricula", "")
    prof_centro = paciente.get("profesional_centro", "")
    prof_email = paciente.get("profesional_email", "")
    grbas_str = paciente.get("grbas", "G0 R0 B0 A0 S0")
    rasati_str = paciente.get("rasati", "R0 A0 S0 A20 T0 I0")

    if prof_name:
        elements.append(Paragraph(f"<b>{prof_name}</b>", title_style))
        subtitle_parts = [p for p in [prof_title, f"Matrícula: {prof_mat}" if prof_mat else "", prof_centro, prof_email] if p]
        if subtitle_parts:
            elements.append(Paragraph(" | ".join(subtitle_parts), subtitle_style))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("PROTOCOLO DE EVALUACIÓN BIOACÚSTICA DE LA VOZ", title_style))
    elements.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"Motor: Praat/Parselmouth {metricas.get('parselmouth_version', 'N/D')}",
        subtitle_style
    ))

    info_data = [
        [Paragraph(f"<b>Paciente:</b> {paciente.get('nombre', 'N/A')}", body_style),
         Paragraph(f"<b>DNI:</b> {paciente.get('dni', 'N/A')}", body_style)],
        [Paragraph(f"<b>Edad:</b> {paciente.get('edad', 'N/A')} años | <b>Sexo:</b> {paciente.get('sexo', 'N/A')}", body_style),
         Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y')}", body_style)],
        [Paragraph(f"<b>Motivo:</b> {paciente.get('motivo', 'N/A')}", body_style),
         Paragraph(f"<b>Derivador:</b> {paciente.get('derivador', 'N/A')}", body_style)],
        [Paragraph(f"<b>GRBAS:</b> {grbas_str}", body_style),
         Paragraph(f"<b>RASATI:</b> {rasati_str}", body_style)],
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
         "Variable (sexo/edad)"],
        ["F0 mínima", f"{metricas.get('f0_min', 'N/D')} Hz", "—", "—"],
        ["F0 máxima", f"{metricas.get('f0_max', 'N/D')} Hz", "—", "—"],
        ["F0 DE", f"{metricas.get('f0_sd', 'N/D')} Hz", "—", "—"],
        ["Jitter local", f"{metricas.get('jitter_pct', 'N/D')}%",
         _severity_cell(metricas.get('jitter_pct'), (1.04, 2.0, 3.0), "%"),
         "< 1.04%"],
        ["Jitter RAP", f"{metricas.get('jitter_rap_pct', 'N/D')}%",
         _severity_cell(metricas.get('jitter_rap_pct'), (1.04, 2.0, 3.0), "%"),
         "< 1.04%"],
        ["Jitter PPQ5", f"{metricas.get('jitter_ppq5_pct', 'N/D')}%",
         _severity_cell(metricas.get('jitter_ppq5_pct'), (0.5, 1.0, 1.5), "%"),
         "< 0.5%"],
        ["Shimmer local", f"{metricas.get('shimmer_pct', 'N/D')}%",
         _severity_cell(metricas.get('shimmer_pct'), (3.81, 5.0, 7.0), "%"),
         "< 3.81%"],
        ["Shimmer (dB)", f"{metricas.get('shimmer_db', 'N/D')} dB",
         _severity_cell(metricas.get('shimmer_db'), (0.5, 1.0, 2.0), " dB"),
         "< 0.5 dB"],
        ["Shimmer APQ3", f"{metricas.get('shimmer_apq3_pct', 'N/D')}%",
         _severity_cell(metricas.get('shimmer_apq3_pct'), (3.0, 4.5, 6.0), "%"),
         "< 3.0%"],
        ["Shimmer APQ5", f"{metricas.get('shimmer_apq5_pct', 'N/D')}%",
         _severity_cell(metricas.get('shimmer_apq5_pct'), (2.5, 4.0, 6.0), "%"),
         "< 2.5%"],
        ["Shimmer APQ11", f"{metricas.get('shimmer_apq11_pct', 'N/D')}%",
         _severity_cell(metricas.get('shimmer_apq11_pct'), (3.0, 5.0, 7.0), "%"),
         "< 3.0%"],
        ["HNR", f"{metricas.get('hnr_db', 'N/D')} dB",
         _severity_cell(metricas.get('hnr_db'), (20, 15, 10), " dB"),
         "> 20 dB"],
        ["CPPS", f"{metricas.get('cpps_db', 'N/D')} dB",
         _severity_cell(metricas.get('cpps_db'), (5.5, 3.0, 1.0), " dB"),
         "> 5.5 dB"],
        ["NNE", f"{metricas.get('nne_db', 'N/D')} dB",
         _severity_cell(metricas.get('nne_db'), (1.5, 2.5, 3.5), " dB"),
         "< 1.5 dB"],
        ["NHR", f"{metricas.get('nhr', 'N/D')}",
         _severity_cell(metricas.get('nhr'), (0.05, 0.15, 0.25), ""),
         "< 0.05"],
        ["F1", f"{metricas.get('f1_hz', 'N/D')} Hz", "—", "Variable"],
        ["F2", f"{metricas.get('f2_hz', 'N/D')} Hz", "—", "Variable"],
        ["Intensidad Media", f"{metricas.get('intensity_mean_db', 'N/D')} dB", "—", "60-80 dB"],
        ["Alpha Ratio", f"{metricas.get('alpha_ratio_db', 'N/D')} dB", "—", "Variable"],
    ]
    t_metrics = Table(metrics_data, colWidths=[95, 95, 145, 140])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("<b>2. AVQI v03.01 — Acoustic Voice Quality Index</b>", section_style))
    avqi_calculable = metricas.get("avqi_calculable", False)
    avqi_val = metricas.get("avqi")
    avqi_status = metricas.get("avqi_status", "ok")

    if avqi_calculable and avqi_val is not None:
        avqi_data = [
            ["Componente", "Resultado", "Unidad"],
            ["CPPS", str(metricas.get('cpps_db', 'N/D')), "dB"],
            ["HNR", str(metricas.get('hnr_db', 'N/D')), "dB"],
            ["Shimmer local", str(metricas.get('shimmer_pct', 'N/D')), "%"],
            ["Spectral Slope", str(metricas.get('spectral_tilt_slope', 'N/D')), "dB/Hz"],
            ["AVQI v03.01", str(avqi_val), ""],
        ]
        t_avqi = Table(avqi_data, colWidths=[200, 160, 80])
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
        avqi_nivel, avqi_clr, avqi_label = _nivel_severidad(avqi_val, (2.0, 2.9, 3.5))
        try:
            avqi_hex = f"#{int(avqi_clr.red*255):02x}{int(avqi_clr.green*255):02x}{int(avqi_clr.blue*255):02x}"
        except Exception:
            avqi_hex = '#334155'
        avqi_style_list.append(('BACKGROUND', (1, 5), (1, 5), colors.HexColor(avqi_hex)))
        avqi_style_list.append(('TEXTCOLOR', (1, 5), (1, 5), colors.white))
        t_avqi.setStyle(TableStyle(avqi_style_list))
        elements.append(t_avqi)
    else:
        elements.append(Paragraph(
            '<font color="#94a3b8"><b>AVQI NO EVALUABLE</b></font> — '
            'Se requiere grabación de vocal sostenida /a/ concatenada con habla continua fonéticamente balanceada.',
            disclaimer_style
        ))

    if avqi_val == 0.0:
        elements.append(Paragraph(
            '<font color="#ef4444"><b>ALERTA:</b></font> '
            'AVQI = 0.0 es un valor sospechosamente bajo. Verificar calidad del audio y validez del análisis.',
            disclaimer_style
        ))

    elements.append(PageBreak())

    if cross_check and cross_check.get("perceptual_acoustic_consistency") != "N/D":
        elements.append(Paragraph("<b>3. Correlación Percepción-Acústica (GRBAS vs Bioacústica)</b>", section_style))
        consistency = cross_check.get("perceptual_acoustic_consistency", "")
        consistency_color = "#22c55e" if consistency == "Consistente" else "#f97316"
        elements.append(Paragraph(f'<font color="{consistency_color}"><b>Consistencia:</b></font> {consistency}', body_style))
        elements.append(Spacer(1, 4))

        if cross_check.get("acoustic_indicators"):
            elements.append(Paragraph("<b>Indicadores acústicos relevantes:</b>", body_style))
            for ind in cross_check["acoustic_indicators"][:5]:
                elements.append(Paragraph(f"• {ind}", small_style))
            elements.append(Spacer(1, 4))

        if cross_check.get("pathology_matches"):
            elements.append(Paragraph("<b>Perfiles clínicos compatibles (referencia, no diagnóstico):</b>", body_style))
            for m in cross_check["pathology_matches"][:2]:
                elements.append(Paragraph(
                    f"• <b>{m['name']}</b> (coincidencia {m['match_score']}/3): {'; '.join(m['matching_indicators'])}",
                    small_style
                ))
            elements.append(Spacer(1, 4))

        if cross_check.get("clinical_observations"):
            elements.append(Paragraph("<b>Observaciones clínicas:</b>", body_style))
            for obs in cross_check["clinical_observations"][:2]:
                elements.append(Paragraph(f"• {obs['pattern']}: {obs['suggestion']}", small_style))
            elements.append(Spacer(1, 4))

        if cross_check.get("alerts"):
            elements.append(Paragraph('<font color="#f97316"><b>Alertas:</b></font>', body_style))
            for alert in cross_check["alerts"][:3]:
                elements.append(Paragraph(f'• <font color="#f97316">{alert}</font>', small_style))
            elements.append(Spacer(1, 4))

    elements.append(Paragraph("<b>4. Gráficos Clínicos de Alta Resolución</b>", section_style))
    chart_embedded = False
    if charts:
        for chart_key, chart_title, chart_h in [
            ("spectrogram_img", "Espectrograma de Banda Estrecha con F0 y Formantes", 280),
            ("spectrum_img", "Espectro de Potencia FFT y Pendiente Espectral", 280),
            ("ddf_img", "Diagrama de Dispersión Fonatoria (DDF)", 280),
            ("radar_img", "VOXplot Radar — Severidad Multifactorial", 350),
        ]:
            img_bytes = _chart_from_b64(charts, chart_key)
            if img_bytes:
                elements.append(Spacer(1, 4))
                elements.append(Paragraph(f"<b>{chart_title}</b>", small_style))
                chart_w = 400 if chart_key == "radar_img" else 500
                elements.append(RLImage(BytesIO(img_bytes), width=chart_w, height=chart_h))
                elements.append(Spacer(1, 6))
                chart_embedded = True
    if not chart_embedded and os.path.exists(img_path):
        elements.append(RLImage(img_path, width=500, height=620))

    elements.append(PageBreak())

    elements.append(Paragraph("<b>4. Interpretación Asistida por IA</b>", section_style))
    sintesis = paciente.get('sintesis_ia', '')
    if sintesis and sintesis.strip():
        for para in sintesis.split('\n'):
            if para.strip():
                elements.append(Paragraph(para, body_style))
    else:
        elements.append(Paragraph(
            '<font color="#64748b"><i>Síntesis descriptiva no disponible temporalmente. '
            'Los resultados bioacústicos fueron calculados correctamente.</i></font>',
            body_style
        ))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>5. Observaciones Fonoaudiológicas</b>", section_style))
    elements.append(Paragraph(
        '<font color="#94a3b8"><i>Espacio para observaciones del profesional. '
        'El contenido puede completarse antes de estampar en el informe definitivo.</i></font>',
        body_style
    ))
    elements.append(Spacer(1, 4))
    for _ in range(8):
        elements.append(Paragraph("_" * 95, body_style))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<b>6. Referencias Bibliográficas y Avisos Clínicos</b>", section_style))
    disclaimers = [
        "Este informe es una herramienta de apoyo y no sustituye la evaluación clínica del profesional fonoaudiólogo.",
        "Los valores bioacústicos son mediciones objetivas. La interpretación diagnóstica es responsabilidad exclusiva del clínico.",
        "Los rangos de referencia son orientativos y dependen de edad, sexo, tarea vocal, contexto y población normativa utilizada.",
        "El AVQI v03.01 fue validado para clasificación de disfonía en adultos. Su aplicabilidad a niños debe considerarse con cautela.",
        "Este sistema no almacena diagnósticos. Todos los resultados son mediciones instrumentales que requieren correlación clínica.",
    ]
    for d in disclaimers:
        elements.append(Paragraph(f"• {d}", disclaimer_style))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<b>Referencias:</b>", body_style))
    refs = [
        "Farías, P. (2012). Ejercicios que restauran la función vocal. Editorial: Editorial de la Universidad de la Plata.",
        "Farías, P. (2016). Guía clínica para el especialista en laringe y voz. Editorial: Adriana Hidalgo Editora.",
        "Maryn, Y. et al. (2010). The Acoustic Voice Quality Index (AVQI). Journal of Speech, Language, and Hearing Research.",
        "Titze, I. R. (1994). Principles of Voice Production. National Center for Voice and Speech.",
        "Titze, I. R. (2000). Principles of Voice Production (2nd printing). Prentice-Hall.",
        "Cecconello, A. et al. Aplicación del análisis acústico en la clínica vocal. Revista Fonoaudiologia.",
        "Feinberg, D. (2022). VoiceLab: A deep learning approach to acoustic voice analysis. Proc. Interspeech 2022.",
    ]
    for ref in refs:
        elements.append(Paragraph(f"• {ref}", small_style))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("_" * 95, disclaimer_style))
    footer_data = [
        [Paragraph(f"<b>Profesional:</b> {prof_name or 'N/D'}", body_style),
         Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", body_style)],
        [Paragraph(f"<b>Matrícula:</b> {prof_mat or 'N/D'}", body_style),
         Paragraph(f"<b>Hash SHA-256:</b> {audio.get('file_hash_sha256', 'N/D')[:32]}...", body_style)],
    ]
    t_footer = Table(footer_data, colWidths=[270, 270])
    t_footer.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_footer)

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>Firma y Sello del Profesional:</b>", body_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("_" * 50, body_style))

    doc.build(elements)
