"""
VocalisLab Pro — Generador de Cuadernillo Terapéutico PDF
Genera PDFs profesionales de ejercicios vocales para el paciente.
"""
import os
import json
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


PRIMARY = HexColor("#1a237e")
SECONDARY = HexColor("#7c4dff")
ACCENT = HexColor("#00c853")
LIGHT_BG = HexColor("#f5f5f5")
DARK_TEXT = HexColor("#212121")
GRAY_TEXT = HexColor("#616161")
LIGHT_GRAY = HexColor("#e0e0e0")


def _get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontSize=28,
        textColor=PRIMARY,
        spaceAfter=6 * mm,
        alignment=TA_CENTER,
        leading=34,
    ))
    styles.add(ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=SECONDARY,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    ))
    styles.add(ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=PRIMARY,
        spaceBefore=8 * mm,
        spaceAfter=4 * mm,
        leading=20,
    ))
    styles.add(ParagraphStyle(
        'ExerciseTitle',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=SECONDARY,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
        leading=16,
    ))
    styles.add(ParagraphStyle(
        'CuadBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DARK_TEXT,
        alignment=TA_JUSTIFY,
        leading=14,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        'StepText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DARK_TEXT,
        leftIndent=8 * mm,
        leading=14,
        spaceAfter=1 * mm,
    ))
    styles.add(ParagraphStyle(
        'ContractTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=PRIMARY,
        spaceBefore=4 * mm,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        'ContractText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DARK_TEXT,
        leading=14,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        'FooterText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=GRAY_TEXT,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'PageNumber',
        parent=styles['Normal'],
        fontSize=9,
        textColor=GRAY_TEXT,
        alignment=TA_CENTER,
    ))

    return styles


def _build_cover(styles, titulo, paciente_nombre, sesiones, fecha):
    elements = []
    elements.append(Spacer(1, 40 * mm))
    elements.append(Paragraph("VOCALISLAB PRO", styles['CoverTitle']))
    elements.append(Paragraph(titulo, styles['CoverSubtitle']))
    elements.append(Spacer(1, 15 * mm))

    info_data = [
        ["Paciente:", paciente_nombre or "Sin especificar"],
        ["Fecha de inicio:", fecha],
        ["Sesiones:", str(sesiones)],
        ["Generado por:", "VocalisLab Pro — Plataforma Fonoaudiológica"],
    ]
    info_table = Table(info_data, colWidths=[45 * mm, 90 * mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), PRIMARY),
        ('TEXTCOLOR', (1, 0), (1, -1), DARK_TEXT),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, LIGHT_GRAY),
    ]))
    elements.append(info_table)
    elements.append(PageBreak())
    return elements


def _build_contract(styles, contrato):
    elements = []
    elements.append(Paragraph("Contrato Terapéutico", styles['ContractTitle']))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 4 * mm))

    if isinstance(contrato, str):
        try:
            contrato = json.loads(contrato)
        except Exception:
            contrato = {}

    if contrato.get("frecuencia"):
        elements.append(Paragraph(
            f"<b>Frecuencia de las sesiones:</b> {contrato['frecuencia']}",
            styles['ContractText']
        ))
    if contrato.get("duracion_sesion"):
        elements.append(Paragraph(
            f"<b>Duración aproximada:</b> {contrato['duracion_sesion']}",
            styles['ContractText']
        ))
    if contrato.get("pautas_ausencias"):
        elements.append(Paragraph(
            f"<b>Pautas de asistencia:</b> {contrato['pautas_ausencias']}",
            styles['ContractText']
        ))

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        "Este cuadernillo ha sido diseñado por su fonoaudiólogo/a de acuerdo a su evaluación clínica. "
        "Los ejercicios deben realizarse con regularidad y sin forzar. En caso de dolor o molestia, "
        "suspender el ejercicio y consultar a su profesional de referencia.",
        styles['ContractText']
    ))

    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="40%", color=LIGHT_GRAY, thickness=0.5))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("Firma del profesional: ___________________________", styles['ContractText']))
    elements.append(Paragraph("Firma del paciente:    ___________________________", styles['ContractText']))
    elements.append(Spacer(1, 4 * mm))

    return elements


def _build_exercise(styles, exercise, idx):
    elements = []
    title = f"{idx}. {exercise.get('name', 'Ejercicio sin nombre')}"
    elements.append(Paragraph(title, styles['ExerciseTitle']))

    desc = exercise.get("description", "")
    if desc:
        elements.append(Paragraph(desc, styles['CuadBody']))

    steps = exercise.get("steps", [])
    if steps:
        for i, step in enumerate(steps, 1):
            step_text = f"<b>Paso {i}:</b> {step}"
            elements.append(Paragraph(step_text, styles['StepText']))

    phrases = exercise.get("phrases", [])
    if phrases:
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("<b>Frases:</b>", styles['CuadBody']))
        for phrase in phrases:
            elements.append(Paragraph(f"• {phrase}", styles['StepText']))

    duration = exercise.get("duration_min", "")
    if duration:
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(
            f"<i>Duración estimada: {duration} minutos</i>",
            styles['CuadBody']
        ))

    elements.append(Spacer(1, 3 * mm))
    elements.append(HRFlowable(width="100%", color=LIGHT_GRAY, thickness=0.5))
    elements.append(Spacer(1, 2 * mm))

    return KeepTogether(elements) if len(elements) <= 8 else elements


def _build_sessions_calendar(styles, sesiones, ejercicios):
    elements = []
    elements.append(Paragraph("Calendario de Sesiones", styles['SectionTitle']))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 4 * mm))

    header = ["Sesión", "Ejercicios", "Estado"]
    data = [header]

    ej_por_sesion = max(1, len(ejercicios) // max(1, sesiones))
    for s in range(1, sesiones + 1):
        inicio = (s - 1) * ej_por_sesion
        fin = min(inicio + ej_por_sesion + 1, len(ejercicios))
        ej_nombres = "\n".join([f"• {e.get('name', '')}" for e in ejercicios[inicio:fin]])
        data.append([str(s), ej_nombres or "Revisión", "Pendiente"])

    table = Table(data, colWidths=[18 * mm, 120 * mm, 28 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
    ]))
    elements.append(table)
    return elements


def _add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(GRAY_TEXT)
    canvas.drawCentredString(A4[0] / 2, 15 * mm, f"Página {doc.page}")
    canvas.setFont('Helvetica', 8)
    canvas.drawString(15 * mm, 15 * mm, "VocalisLab Pro")
    canvas.drawRightString(A4[0] - 15 * mm, 15 * mm, "Plataforma Fonoaudiológica")
    canvas.restoreState()


def generar_cuadernillo_pdf(
    paciente_nombre: str,
    titulo: str,
    sesiones: int,
    ejercicios: list,
    contrato: dict,
    notas: str = "",
) -> str:
    fecha = __import__('datetime').datetime.now().strftime("%d/%m/%Y")

    tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf_path = tmp_file.name
    tmp_file.close()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )

    styles = _get_styles()
    story = []

    story.extend(_build_cover(styles, titulo, paciente_nombre, sesiones, fecha))
    story.extend(_build_contract(styles, contrato))

    story.append(Paragraph("Ejercicios", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    story.append(Spacer(1, 4 * mm))

    for idx, ex in enumerate(ejercicios, 1):
        result = _build_exercise(styles, ex, idx)
        if isinstance(result, list):
            story.extend(result)
        else:
            story.append(result)

    story.append(PageBreak())
    story.extend(_build_sessions_calendar(styles, sesiones, ejercicios))

    if notas:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("Notas del Profesional", styles['SectionTitle']))
        story.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(notas, styles['CuadBody']))

    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        "Este material fue generado por VocalisLab Pro. Distribución restringida al paciente y profesional tratante.",
        styles['FooterText']
    ))

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return pdf_path
