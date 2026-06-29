"""
Génère un PDF PEMD (CERFA) pour l'export du tracker.
Tableau 1 : Caractérisation des PEM identifiés comme potentiellement réemployables.
"""

import os
from io import BytesIO
from typing import List, Dict, Any

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ============================================================
# CHARGEMENT POLICE TTF (support Unicode pour les symboles)
# ============================================================

def _load_unicode_font():
    """Tente de charger une police TTF avec support Unicode."""
    candidates = [
        ("DejaVuSans", "C:/Windows/Fonts/DejaVuSans.ttf"),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("DejaVuSans", "/usr/share/fonts/TTF/DejaVuSans.ttf"),
        ("Arial", "C:/Windows/Fonts/arial.ttf"),
        ("Arial", "/System/Library/Fonts/Arial.ttf"),
        ("Calibri", "C:/Windows/Fonts/calibri.ttf"),
        ("SegoeUI", "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return None


_UNICODE_FONT = _load_unicode_font()

if _UNICODE_FONT:
    _CHECK_SYMBOL = "☑"
    _UNCHECK_SYMBOL = "☐"
    _FONT_NAME = _UNICODE_FONT
else:
    _CHECK_SYMBOL = "[X]"
    _UNCHECK_SYMBOL = "[ ]"
    _FONT_NAME = "Helvetica"


# ============================================================
# STYLES
# ============================================================

def _ps(size: int, align=TA_CENTER, bold=False, color=colors.black, font_name=None):
    fn = font_name or ("Helvetica-Bold" if bold else _FONT_NAME)
    return ParagraphStyle(
        f"s{size}",
        fontName=fn,
        fontSize=size,
        alignment=align,
        textColor=color,
        leading=size + 2,
        wordWrap="LTR",
    )


S_TITLE = _ps(14, bold=True, color=colors.HexColor("#1e3a5f"))
S_TH_MAIN = _ps(9, bold=True, color=colors.white)
S_TH_LEFT = _ps(7, bold=True, color=colors.HexColor("#1e3a5f"))
S_TH_RIGHT = _ps(7, bold=True, color=colors.HexColor("#1e3a5f"))
S_TD = _ps(8, align=TA_LEFT, color=colors.HexColor("#374151"))
S_TD_C = _ps(8, align=TA_CENTER, color=colors.HexColor("#374151"))

BLUE_MAIN = colors.HexColor("#1e3a5f")
BLUE_LIGHT = colors.HexColor("#dbeafe")
BLUE_MID = colors.HexColor("#bfdbfe")
GREY_LIGHT = colors.HexColor("#f3f4f6")
WHITE = colors.white
PURPLE_LIGHT = colors.HexColor("#c7c8e0")
PURPLE_MID = colors.HexColor("#8b8db0")


# ============================================================
# HELPERS
# ============================================================

def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "oui", "vrai")
    if isinstance(value, int):
        return value != 0
    return bool(value)


# ============================================================
# GÉNÉRATION PDF
# ============================================================

def generate_pemd_pdf_from_data(rows: List[Dict[str, Any]], project_name: str = "") -> bytes:
    """Génère un PDF PEMD CERFA avec le tableau exact de l'image."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=0.8 * cm,
        leftMargin=0.8 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    story = []
    story.append(Paragraph(
        f"<b>Tableau 1 — Caractérisation des produits, équipements et matériaux (PEM) "
        f"identifiés comme potentiellement réemployables (4)</b>",
        S_TITLE
    ))
    story.append(Spacer(1, 0.4 * cm))

    header_data = [
        [
            Paragraph("Remplissez ces colonnes", S_TH_MAIN),
            "", "", "", "", "", "", "", "",
            Paragraph(
                "Cochez la case pour indiquer si ces informations sont "
                "renseignées dans votre rapport de diagnostic (14)",
                S_TH_MAIN
            ),
            "", "", "",
        ],
    ]

    col_headers = [
        Paragraph("Catégorie<br/>(5)", S_TH_LEFT),
        Paragraph("Description<br/>(6)", S_TH_LEFT),
        Paragraph("Quantité disponible et unité appropriée<br/>(7)", S_TH_LEFT),
        Paragraph("Dimensions<br/>(8)", S_TH_LEFT),
        Paragraph("Type principal d'assemblage<br/>(9)", S_TH_LEFT),
        Paragraph("Âge estimé<br/>(10)", S_TH_LEFT),
        Paragraph("État de conservation ou de fonctionnement estimé<br/>(11)", S_TH_LEFT),
        Paragraph(
            "Suspectez-vous la présence de substances dangereuses "
            "ou de polluant organique persistant dans ce PEM ?<br/>(12)",
            S_TH_LEFT
        ),
        Paragraph("Matériaux Constitutifs<br/>(13)", S_TH_LEFT),
        Paragraph("Localisation et fonction du PEM dans le bâtiment<br/>(15)", S_TH_RIGHT),
        Paragraph(
            "Conditions techniques et économiques pour permettre le réemploi du PEM<br/>(16)",
            S_TH_RIGHT
        ),
        Paragraph("Informations techniques disponibles<br/>(17)", S_TH_RIGHT),
        Paragraph("Précautions de dépose, transport et stockage<br/>(18)", S_TH_RIGHT),
    ]

    data = [col_headers]
    for r in rows:
        data.append([
            Paragraph(r.get("categorie") or "", S_TD),
            Paragraph(r.get("description") or "", S_TD),
            Paragraph(r.get("quantite") or "", S_TD_C),
            Paragraph(r.get("dimensions") or "", S_TD_C),
            Paragraph(r.get("assemblage") or "", S_TD_C),
            Paragraph(r.get("age_estime") or "", S_TD_C),
            Paragraph(r.get("etat") or "", S_TD_C),
            Paragraph(_CHECK_SYMBOL if _to_bool(r.get("substances_dangereuses")) else _UNCHECK_SYMBOL, S_TD_C),
            Paragraph(r.get("materiaux") or "", S_TD),
            Paragraph(_CHECK_SYMBOL if _to_bool(r.get("localisation")) else _UNCHECK_SYMBOL, S_TD_C),
            Paragraph(_CHECK_SYMBOL if _to_bool(r.get("conditions_reemploi")) else _UNCHECK_SYMBOL, S_TD_C),
            Paragraph(_CHECK_SYMBOL if _to_bool(r.get("infos_techniques")) else _UNCHECK_SYMBOL, S_TD_C),
            Paragraph(_CHECK_SYMBOL if _to_bool(r.get("precautions")) else _UNCHECK_SYMBOL, S_TD_C),
        ])

    page_w = landscape(A4)[0] - 1.6 * cm
    col_widths = [
        page_w * 0.06,  # Catégorie
        page_w * 0.09,  # Description
        page_w * 0.07,  # Quantité  (header long)
        page_w * 0.05,  # Dimensions
        page_w * 0.05,  # Assemblage
        page_w * 0.04,  # Âge estimé (court)
        page_w * 0.07,  # État  (header long)
        page_w * 0.10,  # Substances dangereuses (12)
        page_w * 0.07,  # Matériaux
        page_w * 0.07,  # Localisation (header long)
        page_w * 0.08,  # Conditions réemploi (header long)
        page_w * 0.07,  # Infos techniques
        page_w * 0.08,  # Précautions (header long)
    ]

    full_data = header_data + data
    tbl = Table(full_data, colWidths=col_widths, repeatRows=2)

    style_cmds = [
        ("BACKGROUND", (0, 0), (8, 0), BLUE_MAIN),
        ("BACKGROUND", (9, 0), (12, 0), PURPLE_MID),
        ("TEXTCOLOR", (0, 0), (12, 0), colors.white),
        ("SPAN", (0, 0), (8, 0)),
        ("SPAN", (9, 0), (12, 0)),
        ("VALIGN", (0, 0), (12, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (12, 0), 6),
        ("BOTTOMPADDING", (0, 0), (12, 0), 6),
        ("LEFTPADDING", (0, 0), (12, 0), 4),
        ("BACKGROUND", (0, 1), (8, 1), BLUE_MID),
        ("BACKGROUND", (9, 1), (12, 1), PURPLE_LIGHT),
        ("TEXTCOLOR", (0, 1), (12, 1), colors.HexColor("#1e3a5f")),
        ("VALIGN", (0, 1), (12, 1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (12, 1), 6),
        ("BOTTOMPADDING", (0, 1), (12, 1), 6),
        ("LEFTPADDING", (0, 1), (12, 1), 3),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e3a5f")),
        ("VALIGN", (0, 2), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 2), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 3),
        ("LEFTPADDING", (0, 2), (-1, -1), 3),
    ]

    for i, row in enumerate(data[1:], 2):
        bg = GREY_LIGHT if i % 2 == 0 else WHITE
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()
