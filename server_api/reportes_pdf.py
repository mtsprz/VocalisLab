import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generar_pdf_clinico(paciente: dict, metricas: dict, img_path: str, pdf_path: str):
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=12
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6,
        leading=13
    )
    
    elements = [
        Paragraph("VocalisLab — Reporte Bioacústico Vocal", title_style),
        Paragraph("Evaluación Fonoaudiológica Computarizada (AVQI v03.01 | Praat | VOXplot | VoxMetria)", subtitle_style),
        Spacer(1, 6),
    ]
    
    # Patient Info Table
    info_data = [
        [Paragraph(f"<b>Paciente:</b> {paciente.get('nombre', 'N/A')}", body_style),
         Paragraph(f"<b>DNI:</b> {paciente.get('dni', 'N/A')}", body_style)],
        [Paragraph(f"<b>Edad:</b> {paciente.get('edad', 'N/A')} años | <b>Sexo:</b> {paciente.get('sexo', 'N/A')}", body_style),
         Paragraph(f"<b>TMF:</b> {paciente.get('tmf', '0')} s", body_style)],
        [Paragraph(f"<b>Motivo:</b> {paciente.get('motivo', 'N/A')}", body_style),
         Paragraph(f"<b>Derivador:</b> {paciente.get('derivador', 'N/A')}", body_style)]
    ]
    t = Table(info_data, colWidths=[270, 270])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))
    
    # Metrics Table
    elements.append(Paragraph("<b>Métricas Bioacústicas y Origen de Extracción</b>", body_style))
    metrics_data = [
        ["Parámetro", "Valor", "Origen Software", "Referencia Normal"],
        ["F0 Media", f"{metricas['f0_mean']} Hz", "Praat (Parselmouth)", "Variable (100-250 Hz)"],
        ["Jitter local", f"{metricas['jitter_pct']}%", "Praat (Parselmouth)", "< 1.04%"],
        ["Shimmer local", f"{metricas['shimmer_pct']}%", "Praat (Parselmouth)", "< 3.81%"],
        ["HNR", f"{metricas['hnr_db']} dB", "Praat (Parselmouth)", "> 20 dB"],
        ["CPPS", f"{metricas['cpps_db']} dB", "VoxMetria / Praat", "> 5.5 dB"],
        ["AVQI v03.01", f"{metricas['avqi']}", "Algoritmo Integrado", "< 2.9 (Normovis)"]
    ]
    t_metrics = Table(metrics_data, colWidths=[120, 90, 165, 165])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#ffffff')),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 10))
    
    # Chart Image
    if os.path.exists(img_path):
        elements.append(Paragraph("<b>Diagrama de Desviación Fonatoria (DDF) y Espectrograma</b>", body_style))
        elements.append(RLImage(img_path, width=420, height=160))
        elements.append(Spacer(1, 10))
        
    # AI Synthesis
    elements.append(Paragraph("<b>Síntesis Diagnóstica (IA - Rioplatense)</b>", body_style))
    synthesis = paciente.get('sintesis_ia', 'Sin sintesis disponible.')
    for para in synthesis.split('\n'):
        if para.strip():
            elements.append(Paragraph(para, body_style))
            
    doc.build(elements)
