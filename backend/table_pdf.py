"""
Génération PDF générique à partir d'un titre, d'en-têtes et de lignes.
Utilisé pour l'export PDF des tableaux IFC (tout, sélection, inertes, équipements).
"""

import io
from typing import List

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)

_BLUE  = colors.HexColor("#1e3a5f")
_LBLUE = colors.HexColor("#dbeafe")
_GREY  = colors.HexColor("#f3f4f6")
_WHITE = colors.white
_DARK  = colors.HexColor("#374151")


def generate_table_pdf(title: str, headers: List[str], rows: List[List[str]]) -> bytes:
    """
    Génère un PDF avec un tableau simple.
    - title   : titre affiché en haut
    - headers : liste des noms de colonnes
    - rows    : liste de lignes (chaque ligne = liste de valeurs str)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.2*cm, leftMargin=1.2*cm,
        topMargin=1.5*cm, bottomMargin=1.2*cm,
    )

    s_title = ParagraphStyle("T", fontSize=13, fontName="Helvetica-Bold",
                              textColor=_WHITE, alignment=TA_CENTER)
    s_th    = ParagraphStyle("TH", fontSize=7.5, fontName="Helvetica-Bold",
                              textColor=_WHITE, alignment=TA_CENTER)
    s_td    = ParagraphStyle("TD", fontSize=7, fontName="Helvetica",
                              textColor=_DARK, leading=9)
    s_sub   = ParagraphStyle("S", fontSize=8, fontName="Helvetica",
                              textColor=colors.HexColor("#93c5fd"),
                              alignment=TA_CENTER)

    story = []

    # Titre
    cover = Table(
        [[Paragraph(title, s_title)],
         [Paragraph(f"{len(rows)} élément(s)", s_sub)]],
        colWidths=[26*cm]
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cover)
    story.append(Spacer(1, 0.5*cm))

    if not rows:
        story.append(Paragraph("Aucun élément à afficher.", s_td))
        doc.build(story)
        return buf.getvalue()

    # Largeur automatique des colonnes
    n_cols  = len(headers)
    page_w  = landscape(A4)[0] - 2.4*cm
    col_w   = [page_w / n_cols] * n_cols

    # Construction du tableau
    tdata = [[Paragraph(h, s_th) for h in headers]]
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0), _BLUE),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]

    _TOTAL_FILL = colors.HexColor("#1e3a5f")
    _TOTAL_FONT = ParagraphStyle("TOT", fontSize=7.5, fontName="Helvetica-Bold",
                                  textColor=_WHITE, leading=9)

    for ri, row in enumerate(rows, 1):
        is_total = str(row[0]).startswith("★")
        if is_total:
            cell_style = _TOTAL_FONT
            bg = _TOTAL_FILL
        else:
            cell_style = s_td
            bg = _GREY if ri % 2 == 0 else _WHITE
        tdata.append([Paragraph(str(v) if v is not None else "—", cell_style) for v in row])
        style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), bg))

    tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()
