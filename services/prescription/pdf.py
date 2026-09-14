"""
MedScript Prescription PDF Document Generator
"""

import io
import ast
from reportlab.pdfgen import canvas


def generate_prescription_pdf(text):
    """
    Cleans formatted prescription text and renders a multi-page PDF stream using ReportLab.
    Returns io.BytesIO buffer.
    """
    def clean_list_lines(lines):
        cleaned = []
        for line in lines:
            if line.strip().startswith("- [") and line.strip().endswith("]"):
                try:
                    items = ast.literal_eval(line.strip()[2:].strip())
                    if isinstance(items, list):
                        for item in items:
                            cleaned.append(f"- {item}")
                        continue
                except Exception:
                    pass
            cleaned.append(line)
        return cleaned

    lines = (text or "").split('\n')
    lines = [line.rstrip() for line in lines]
    lines = clean_list_lines(lines)

    final_lines = []
    prev_blank = False
    for line in lines:
        if line.strip() == "---":
            final_lines.append("-" * 40)
            prev_blank = False
        elif line.strip() == "":
            if not prev_blank:
                final_lines.append("")
                prev_blank = True
        else:
            final_lines.append(line)
            prev_blank = False

    final_lines = [line.replace("■", "") for line in final_lines]

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica", 12)
    y_position = 800

    for line in final_lines:
        pdf.drawString(50, y_position, line)
        y_position -= 20
        if y_position < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y_position = 800

    pdf.save()
    buffer.seek(0)
    return buffer
