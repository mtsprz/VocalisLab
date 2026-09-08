import os
import base64
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def _fmt(val, decimals=2, suffix=""):
    if val is None or val == "N/D":
        return "N/D"
    if isinstance(val, (int, float)):
        return f"{val:.{decimals}f}{suffix}"
    return f"{val}{suffix}"


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


def _severity_cell_text(valor, umbrales, unit=""):
    nivel, clr, label = _nivel_severidad(valor, umbrales)
    if valor is None:
        return '<font color="#94a3b8">N/D</font>'
    try:
        hex_clr = f"#{int(clr.red*255):02x}{int(clr.green*255):02x}{int(clr.blue*255):02x}"
    except Exception:
        hex_clr = '#334155'
    val_str = _fmt(valor, 2, unit)
    return f'<font color="{hex_clr}"><b>[{nivel}]</b> {label}</font> ({val_str})'


def _f0_severity_cell(metricas, cross_check):
    """Generate F0 severity cell using age/sex normative data from cross_check."""
    f0 = metricas.get("f0_mean")
    if f0 is None:
        return '<font color="#94a3b8"><b>[—]</b> N/D</font> (N/D)'

    f0_norm = None
    if cross_check:
        f0_norm = cross_check.get("f0_normative")

    if not f0_norm or f0_norm.get("typical_hz") is None:
        return '<font color="#94a3b8"><b>[—]</b> Sin ref.</font> (sin datos normativos)'

    typical = f0_norm["typical_hz"]
    if typical <= 0:
        return '<font color="#94a3b8"><b>[—]</b> N/D</font>'

    deviation_pct = abs(f0 - typical) / typical * 100
    mild = f0_norm.get("mild_pct", 15)
    moderate = f0_norm.get("moderate_pct", 30)
    severe = f0_norm.get("severe_pct", 50)

    if deviation_pct <= mild:
        nivel, hex_clr, label = "0", "#22c55e", "Normal"
    elif deviation_pct <= moderate:
        nivel, hex_clr, label = "1", "#eab308", "Leve"
    elif deviation_pct <= severe:
        nivel, hex_clr, label = "2", "#f97316", "Moderado"
    else:
        nivel, hex_clr, label = "3", "#ef4444", "Marcado"

    direction = "↑" if f0 > typical else "↓"
    return f'<font color="{hex_clr}"><b>[{nivel}]</b> {label}</font> ({_fmt(f0)} Hz {direction} {_fmt(typical, 0)} Hz típ.)'


def _chart_from_b64(charts, key):
    if not charts:
        return None
    chart_data = charts.get(key, "")
    if chart_data and "base64," in chart_data:
        b64_str = chart_data.split("base64,")[1]
        return base64.b64decode(b64_str)
    return None


def _analisis_espectrograma(metricas):
    f0 = metricas.get('f0_mean')
    f0_sd = metricas.get('f0_sd')
    f1 = metricas.get('f1_hz')
    f2 = metricas.get('f2_hz')
    hnr = metricas.get('hnr_db')

    txt = "<b>Observación Bioacústica — Espectrograma de Banda Estrecha:</b><br/>"
    if f0 is not None:
        estabilidad = "muy estable" if (f0_sd and f0_sd < 2.0) else "con variabilidad moderada" if (f0_sd and f0_sd < 5.0) else "con inestabilidad melódica significativa"
        txt += f"• <b>Frecuencia Fundamental (F0 - línea azul):</b> Trazo medio en {_fmt(f0)} Hz ({estabilidad}, DE = {_fmt(f0_sd)} Hz).<br/>"
    else:
        txt += "• <b>Contorno de Pitch:</b> Inestabilidad o pérdida parcial de sonoridad en el contorno de F0.<br/>"

    if f1 and f2:
        txt += f"• <b>Formantes F1-F4 (puntos rojos):</b> Estructura de resonancia supraglótica identificada en F1 = {_fmt(f1, 0)} Hz, F2 = {_fmt(f2, 0)} Hz.<br/>"
    else:
        txt += "• <b>Formantes F1-F4:</b> Pobre definición formántica, sugerente de componente aperiódico o ruido supraglótico.<br/>"

    if hnr is not None:
        noise = "conservación del piso de ruido con armónicos bien definidos" if hnr >= 18 else "presencia de componente de ruido interarmónico en bandas superiores"
        txt += f"• <b>Definición Espectral:</b> {noise} (HNR = {_fmt(hnr)} dB)."
    return txt


def _analisis_espectro(metricas):
    slope = metricas.get('spectral_slope')
    hnr = metricas.get('hnr_db')
    f0 = metricas.get('f0_mean')

    txt = "<b>Observación Bioacústica — Espectro FFT y Pendiente Espectral:</b><br/>"
    if slope is not None:
        cierre = "cierre glótico adecuado y aducción eficiente" if slope > -10.0 else "fuga de aire o cierre incompleto con atenuación rápida en altas frecuencias"
        txt += f"• <b>Pendiente Espectral (Spectral Tilt):</b> {_fmt(slope*1000 if abs(slope)<1 else slope)} dB/kHz. Indica {cierre}.<br/>"
    else:
        txt += "• <b>Pendiente Espectral:</b> No calculable.<br/>"

    if f0 is not None:
        txt += f"• <b>Estructura Armónica FFT:</b> Pico fundamental F0 identificado en {_fmt(f0, 0)} Hz. "
        if hnr is not None and hnr >= 15:
            txt += "Preservación de armónicos primarios sobre la línea base de ruido."
        else:
            txt += "Atenuación severa de la energía armónica por presencia de ruido de turbulencia."
    return txt


def _analisis_ddf(metricas):
    cpps = metricas.get('cpps_db')
    hnr = metricas.get('hnr_db')

    txt = "<b>Observación Bioacústica — Diagrama de Dispersión Fonatoria (DDF):</b><br/>"
    if cpps is not None and hnr is not None:
        if cpps >= 14.5 and hnr >= 20:
            zona = "Normatividad (Zona Verde)"
            desc = "periodicidad glótica adecuada y prominencia cepstral dentro de rango normal"
        elif cpps >= 12.0 and hnr >= 15:
            zona = "Disfonía Leve (Zona Amarilla)"
            desc = "discreta reducción en la prominencia cepstral con aperiodicidad leve"
        else:
            zona = "Fuera de Norma / Disfonía Moderada-Severa"
            desc = "alteración significativa en la periodicidad de la onda mucosa"
        txt += f"• <b>Cuadrante Fonatorio:</b> Ubicación en <b>{zona}</b> (CPPS = {_fmt(cpps)} dB, HNR = {_fmt(hnr)} dB). Caracterizado por {desc}."
    else:
        txt += "• <b>Cuadrante Fonatorio:</b> Datos bioacústicos insuficientes para ubicar en el diagrama DDF."
    return txt


def _analisis_radar(metricas, cross_check):
    avqi = metricas.get('avqi')
    cpps = metricas.get('cpps_db')
    hnr = metricas.get('hnr_db')
    jitter = metricas.get('jitter_pct')

    txt = "<b>Observación Bioacústica — Perfil VOXplot Radar Multifactorial:</b><br/>"
    txt += "• <b>Geometría del Polígono:</b> "
    if cpps is not None and cpps < 14.5 and jitter is not None and jitter > 1.0:
        txt += "Deformación orientada hacia el eje de <b>Hoarseness (Ronquedad)</b> por aumento de Jitter e inestabilidad de la onda mucosa.<br/>"
    elif avqi is not None and avqi > 2.95:
        txt += "Deformación orientada hacia el eje de <b>Breathiness (Soplosidad)</b> por elevación del índice AVQI y fuga glótica.<br/>"
    else:
        txt += "Polígono circunscrito dentro del disco verde de normatividad.<br/>"

    if cross_check and cross_check.get("perceptual_acoustic_consistency") != "N/D":
        txt += f"• <b>Consistencia Clínica:</b> Correlación perceptual-acústica <b>{cross_check.get('perceptual_acoustic_consistency')}</b>."
    return txt


def generar_pdf_clinico(paciente: dict, metricas: dict, img_path: str, pdf_path: str, charts: dict = None, cross_check: dict = None):
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=13, textColor=colors.HexColor('#0f172a'), spaceAfter=3, alignment=1)
    subtitle_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748b'), spaceAfter=8, alignment=1)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=10, textColor=colors.HexColor('#0f172a'), spaceBefore=8, spaceAfter=5)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#334155'), spaceAfter=3, leading=11)
    small_style = ParagraphStyle('SmallStyle', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#334155'), spaceAfter=2, leading=9.5)
    disclaimer_style = ParagraphStyle('DisclaimerStyle', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#64748b'), spaceAfter=2, leading=9, borderColor=colors.HexColor('#e2e8f0'), borderWidth=0.5, borderPadding=3)
    chart_box_style = ParagraphStyle('ChartBoxStyle', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#1e293b'), spaceAfter=2, leading=10.5, backgroundColor=colors.HexColor('#f8fafc'), borderColor=colors.HexColor('#cbd5e1'), borderWidth=0.5, borderPadding=5)

    cell_style = ParagraphStyle('TableCellStyle', parent=styles['Normal'], fontSize=7, leading=8.5, textColor=colors.HexColor('#334155'))
    header_style = ParagraphStyle('TableHeaderStyle', parent=styles['Normal'], fontSize=7.5, leading=9, textColor=colors.white, fontName='Helvetica-Bold')

    def P(txt, st=cell_style):
        return Paragraph(str(txt), st)

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

    elements.append(Paragraph("PROTOCOLO DE EVALUACIÓN BIOACÚSTICA DE LA VOZ", title_style))
    elements.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"Motor: Praat/Parselmouth {metricas.get('parselmouth_version', '0.4.3')}",
        subtitle_style
    ))

    info_data = [
        [P(f"<b>Paciente:</b> {paciente.get('nombre', 'N/A')}", body_style),
         P(f"<b>DNI:</b> {paciente.get('dni', 'N/A')}", body_style)],
        [P(f"<b>Edad:</b> {paciente.get('edad', 'N/A')} años | <b>Sexo:</b> {paciente.get('sexo', 'N/A')}", body_style),
         P(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y')}", body_style)],
        [P(f"<b>Motivo:</b> {paciente.get('motivo', 'N/A')}", body_style),
         P(f"<b>Derivador:</b> {paciente.get('derivador', 'N/A')}", body_style)],
        [P(f"<b>GRBAS:</b> {grbas_str}", body_style),
         P(f"<b>RASATI:</b> {rasati_str}", body_style)],
        [P(f"<b>Audio:</b> SR={audio.get('sample_rate_hz', 'N/D')} Hz, Dur={_fmt(audio.get('duration_s'))}s, RMS={_fmt(audio.get('rms'), 4)}", body_style),
         P(f"<b>Hash:</b> {audio.get('file_hash_sha256', 'N/D')[:16]}...", body_style)],
    ]
    t_info = Table(info_data, colWidths=[260, 260])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 6))

    if not audio.get("valid", True):
        issues_text = " | ".join(audio.get("issues", []))
        elements.append(Paragraph(f'<font color="#ef4444"><b>ALERTA DE CALIDAD DE AUDIO:</b></font> {issues_text}', disclaimer_style))
        elements.append(Spacer(1, 4))

    elements.append(Paragraph("<b>1. Métricas Bioacústicas Principales</b>", section_style))
    metrics_data = [
        [P("Parámetro", header_style), P("Valor", header_style), P("Severidad", header_style), P("Referencia", header_style)],
        [P("F0 media"), P(f"{_fmt(metricas.get('f0_mean'))} Hz"), P(_f0_severity_cell(metricas, cross_check)), P("Según edad/sexo")],
        [P("F0 mínima"), P(f"{_fmt(metricas.get('f0_min'))} Hz"), P("—"), P("—")],
        [P("F0 máxima"), P(f"{_fmt(metricas.get('f0_max'))} Hz"), P("—"), P("—")],
        [P("F0 DE"), P(f"{_fmt(metricas.get('f0_sd'))} Hz"), P("—"), P("—")],
        [P("Jitter local"), P(f"{_fmt(metricas.get('jitter_pct'))}%"), P(_severity_cell_text(metricas.get('jitter_pct'), (1.04, 2.0, 3.0), "%")), P("< 1.04%")],
        [P("Jitter RAP"), P(f"{_fmt(metricas.get('jitter_rap_pct'))}%"), P(_severity_cell_text(metricas.get('jitter_rap_pct'), (1.04, 2.0, 3.0), "%")), P("< 1.04%")],
        [P("Jitter PPQ5"), P(f"{_fmt(metricas.get('jitter_ppq5_pct'))}%"), P(_severity_cell_text(metricas.get('jitter_ppq5_pct'), (0.5, 1.0, 1.5), "%")), P("< 0.5%")],
        [P("Shimmer local"), P(f"{_fmt(metricas.get('shimmer_pct'))}%"), P(_severity_cell_text(metricas.get('shimmer_pct'), (3.81, 5.0, 7.0), "%")), P("< 3.81%")],
        [P("Shimmer (dB)"), P(f"{_fmt(metricas.get('shimmer_db'))} dB"), P(_severity_cell_text(metricas.get('shimmer_db'), (0.5, 1.0, 2.0), " dB")), P("< 0.5 dB")],
        [P("Shimmer APQ3"), P(f"{_fmt(metricas.get('shimmer_apq3_pct'))}%"), P(_severity_cell_text(metricas.get('shimmer_apq3_pct'), (3.0, 4.5, 6.0), "%")), P("< 3.0%")],
        [P("Shimmer APQ5"), P(f"{_fmt(metricas.get('shimmer_apq5_pct'))}%"), P(_severity_cell_text(metricas.get('shimmer_apq5_pct'), (2.5, 4.0, 6.0), "%")), P("< 2.5%")],
        [P("Shimmer APQ11"), P(f"{_fmt(metricas.get('shimmer_apq11_pct'))}%"), P(_severity_cell_text(metricas.get('shimmer_apq11_pct'), (3.0, 5.0, 7.0), "%")), P("< 3.0%")],
        [P("HNR"), P(f"{_fmt(metricas.get('hnr_db'))} dB"), P(_severity_cell_text(metricas.get('hnr_db'), (20, 15, 10), " dB")), P("> 20 dB")],
        [P("CPPS"), P(f"{_fmt(metricas.get('cpps_db'))} dB"), P(_severity_cell_text(metricas.get('cpps_db'), (5.5, 3.0, 1.0), " dB")), P("> 5.5 dB")],
        [P("NNE"), P(f"{_fmt(metricas.get('nne_db'))} dB"), P(_severity_cell_text(metricas.get('nne_db'), (1.5, 2.5, 3.5), " dB")), P("< 1.5 dB")],
        [P("NHR"), P(f"{_fmt(metricas.get('nhr'))}"), P(_severity_cell_text(metricas.get('nhr'), (0.05, 0.15, 0.25), "")), P("< 0.05")],
        [P("F1"), P(f"{_fmt(metricas.get('f1_hz'), 0)} Hz"), P("—"), P("Variable")],
        [P("F2"), P(f"{_fmt(metricas.get('f2_hz'), 0)} Hz"), P("—"), P("Variable")],
        [P("Intensidad Media"), P(f"{_fmt(metricas.get('intensity_mean_db'))} dB"), P("—"), P("60-80 dB")],
        [P("Alpha Ratio"), P(f"{_fmt(metricas.get('alpha_ratio_db'))} dB"), P("—"), P("Variable")],
    ]
    t_metrics = Table(metrics_data, colWidths=[95, 80, 185, 160])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>2. AVQI v03.01 — Acoustic Voice Quality Index</b>", section_style))
    avqi_calculable = metricas.get("avqi_calculable", False)
    avqi_val = metricas.get("avqi")

    if avqi_calculable and avqi_val is not None:
        avqi_data = [
            [P("Componente", header_style), P("Resultado", header_style), P("Unidad", header_style)],
            [P("CPPS"), P(_fmt(metricas.get('cpps_db'))), P("dB")],
            [P("HNR"), P(_fmt(metricas.get('hnr_db'))), P("dB")],
            [P("Shimmer local"), P(_fmt(metricas.get('shimmer_pct'))), P("%")],
            [P("Spectral Slope"), P(_fmt(metricas.get('spectral_slope'))), P("dB/Hz")],
            [P("<b>AVQI v03.01</b>"), P(f"<b>{_fmt(avqi_val)}</b>"), P("")],
        ]
        t_avqi = Table(avqi_data, colWidths=[200, 200, 120])
        t_avqi.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#eff6ff')]),
        ]))
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

        f0_norm = cross_check.get("f0_normative")
        if f0_norm and f0_norm.get("typical_hz"):
            elements.append(Paragraph(
                f'<font color="#1e40af"><b>Referencia F0:</b></font> '
                f'Típico = {f0_norm["typical_hz"]} Hz | '
                f'Rango = {f0_norm["min_hz"]}-{f0_norm["max_hz"]} Hz | '
                f'Severidad: ≤{f0_norm["mild_pct"]}% Normal, ≤{f0_norm["moderate_pct"]}% Leve, '
                f'≤{f0_norm["severe_pct"]}% Moderado, >{f0_norm["severe_pct"]}% Marcado | '
                f'Fuente: {f0_norm.get("source", "Colton et al.")}',
                small_style
            ))
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
            for alert in cross_check["alerts"][:2]:
                elements.append(Paragraph(f'• <font color="#f97316">{alert}</font>', small_style))
            elements.append(Spacer(1, 4))

    elements.append(Paragraph("<b>4. Gráficos Clínicos de Alta Resolución y Análisis Individual</b>", section_style))
    chart_embedded = False
    if charts:
        chart_configs = [
            ("spectrogram_img", "Espectrograma de Banda Estrecha con F0 y Formantes", _analisis_espectrograma(metricas)),
            ("spectrum_img", "Espectro de Potencia FFT y Pendiente Espectral (Tilt)", _analisis_espectro(metricas)),
            ("ddf_img", "Diagrama de Dispersión Fonatoria (DDF - CPPS vs HNR)", _analisis_ddf(metricas)),
            ("radar_img", "VOXplot Radar — Severidad Multifactorial", _analisis_radar(metricas, cross_check)),
        ]
        for chart_key, chart_title, analysis_text in chart_configs:
            img_bytes = _chart_from_b64(charts, chart_key)
            if img_bytes:
                chart_w = 440 if chart_key == "radar_img" else 480
                chart_h = 210 if chart_key == "radar_img" else 180
                block = [
                    Paragraph(f"<b>{chart_title}</b>", small_style),
                    Spacer(1, 2),
                    RLImage(BytesIO(img_bytes), width=chart_w, height=chart_h),
                    Spacer(1, 3),
                    Paragraph(analysis_text, chart_box_style),
                    Spacer(1, 8),
                ]
                elements.append(KeepTogether(block))
                chart_embedded = True

    if not chart_embedded and os.path.exists(img_path):
        elements.append(RLImage(img_path, width=480, height=580))

    elements.append(PageBreak())

    elements.append(Paragraph("<b>5. Interpretación Asistida por IA</b>", section_style))
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

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<b>6. Observaciones Fonoaudiológicas</b>", section_style))
    elements.append(Paragraph(
        '<font color="#94a3b8"><i>Espacio para observaciones del profesional tratante. '
        'El contenido puede completarse antes de estampar en el informe definitivo.</i></font>',
        body_style
    ))
    elements.append(Spacer(1, 3))
    for _ in range(6):
        elements.append(Paragraph("_" * 95, body_style))

    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>7. Referencias Bibliográficas y Avisos Clínicos</b>", section_style))
    disclaimers = [
        "Este informe es una herramienta de apoyo instrumental y no sustituye la evaluación clínica del profesional fonoaudiólogo.",
        "Los valores bioacústicos son mediciones objetivas. La interpretación diagnóstica es responsabilidad exclusiva del clínico.",
        "Los rangos de referencia son orientativos y dependen de edad, sexo, tarea vocal, contexto y población normativa utilizada.",
        "El AVQI v03.01 fue validado para clasificación de disfonía en adultos. Su aplicabilidad a niños debe considerarse con cautela.",
        "Este sistema no almacena diagnósticos. Todos los resultados son mediciones instrumentales que requieren correlación clínica.",
    ]
    for d in disclaimers:
        elements.append(Paragraph(f"• {d}", disclaimer_style))

    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<b>Referencias Bibliográficas:</b>", body_style))
    refs = [
        "Farías, P. (2012). Ejercicios que restauran la función vocal. Editorial de la Universidad de la Plata.",
        "Farías, P. (2016). Guía clínica para el especialista en laringe y voz. Adriana Hidalgo Editora.",
        "Maryn, Y. et al. (2010). The Acoustic Voice Quality Index (AVQI). Journal of Speech, Language, and Hearing Research.",
        "Titze, I. R. (1994). Principles of Voice Production. National Center for Voice and Speech.",
        "Feinberg, D. (2022). VoiceLab: A deep learning approach to acoustic voice analysis. Proc. Interspeech 2022.",
    ]
    for ref in refs:
        elements.append(Paragraph(f"• {ref}", small_style))

    elements.append(Spacer(1, 15))
    elements.append(Paragraph("_" * 95, disclaimer_style))
    footer_data = [
        [P(f"<b>Profesional:</b> {prof_name or 'N/D'}", body_style),
         P(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", body_style)],
        [P(f"<b>Matrícula:</b> {prof_mat or 'N/D'}", body_style),
         P(f"<b>Hash SHA-256:</b> {audio.get('file_hash_sha256', 'N/D')[:32]}...", body_style)],
    ]
    t_footer = Table(footer_data, colWidths=[260, 260])
    t_footer.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_footer)

    elements.append(Spacer(1, 25))
    elements.append(Paragraph("<b>Firma y Sello del Profesional:</b>", body_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("_" * 50, body_style))

    doc.build(elements)
