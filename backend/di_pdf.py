"""
Génération du PDF « Déchets Inertes (DI) » au format CERFA.
Mise en page : paysage (landscape), table multi-colonnes avec case à cocher.
Structure exacte du formulaire CERFA avec 3 lignes de header.
"""
from __future__ import annotations

import io
from typing import List, Dict

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── Police Unicode pour case à cocher ──────────────────────
_CHECKED = "☑"
_UNCHECKED = "☐"
_HAS_UNICODE_FONT = False

try:
    _ = TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    pdfmetrics.registerFont(_)
    _HAS_UNICODE_FONT = True
except Exception:
    try:
        _ = TTFont("DejaVuSans", "C:/Windows/Fonts/DejaVuSans.ttf")
        pdfmetrics.registerFont(_)
        _HAS_UNICODE_FONT = True
    except Exception:
        pass

def _cb(val: bool) -> str:
    """Case à cocher (si police disponible, sinon [X] / [ ])."""
    if _HAS_UNICODE_FONT:
        return _CHECKED if val else _UNCHECKED
    return "[X]" if val else "[ ]"


# ── Police et styles communs ───────────────────────────────

_CELL_FONT = "DejaVuSans" if _HAS_UNICODE_FONT else "Helvetica"
_CELL_FONT_SIZE = 6

_HEADER_STYLE = ParagraphStyle(
    "header_style",
    fontName=_CELL_FONT,
    fontSize=7,
    leading=8,
    alignment=1,
    wordWrap="LTR",
)

_CAT_STYLE = ParagraphStyle(
    "cat_style",
    fontName=_CELL_FONT,
    fontSize=_CELL_FONT_SIZE,
    leading=_CELL_FONT_SIZE + 1,
    wordWrap="LTR",
)


# ── Helpers ────────────────────────────────────────────────

def _to_num(v) -> str:
    if v is None or v == "":
        return ""
    try:
        return f"{round(float(v), 1):.1f}".rstrip("0").rstrip(".") or "0"
    except Exception:
        return str(v)


# ── PDF ────────────────────────────────────────────────────

def generate_di_pdf(
    project_name: str,
    rows: List[Dict],
    metadata: Dict = None,
) -> bytes:
    """Génère le PDF CERFA DI (landscape) avec structure exacte du formulaire."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=0.6 * cm,
        leftMargin=0.6 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.fontSize = 14
    title_style.spaceAfter = 6

    cell_font = _CELL_FONT
    cell_font_size = _CELL_FONT_SIZE
    header_style = _HEADER_STYLE
    cat_style = _CAT_STYLE

    story = []

    # Titre
    story.append(Paragraph(f"<b>Bilan Déchets Inertes (DI)</b>", title_style))
    story.append(Paragraph(f"Projet : {project_name}", styles["Normal"]))
    story.append(Spacer(1, 6))

    # ── Construction des 3 lignes de header ─────────────────

    def _h(text, size=7, bold=True):
        b = "<b>" if bold else ""
        be = "</b>" if bold else ""
        return Paragraph(f"<font name='{cell_font}' size='{size}'>{b}{text}{be}</font>", header_style)

    # Ligne 0 – Groupes CERFA
    header_row0 = [
        _h("Identification des déchets", 8),
        "", "", "",
        _h("Destination (21)", 8),
        _h("Valorisation (22)", 8),
        "", "", "",
        _h("Élimination (22)", 8),
        "",
        _h("Conditions techniques", 8),
    ]

    # Ligne 1 – Sous-groupes (texte long; les colonnes sans sous-groupe span avec ligne 2)
    header_row1 = [
        _h("Catégorie"),          # 0  → span vertical (0,1)-(0,2)
        _h("Code déchet"),         # 1  → span vertical (1,1)-(1,2)
        _h("Quantité estimée (20)", 7),  # 2  → span horizontal (2,1)-(3,1)
        "",                        # 3  (vide, span horizontal depuis 2)
        _h("Le diagnostic identifie-t-il les filières et exutoires possibles ?<br/>cochez pour oui", 6),  # 4 → span vertical (4,1)-(4,2)
        _h("Valorisation matière"),  # 5 → span horizontal (5,1)-(7,1)
        "",                         # 6 (vide, span horizontal depuis 5)
        "",                         # 7 (vide, span horizontal depuis 5)
        _h("Valorisation énergétique"),  # 8 → PAS de span vertical (texte différent ligne 2)
        _h("% Incinération sans valorisation énergétique", 6),  # 9 → span vertical (9,1)-(9,2)
        _h("% Non valorisable, à enfouir", 6),  # 10 → span vertical (10,1)-(10,2)
        _h("Le diagnostic identifie-t-il les conditions économiques et techniques nécessaires à la valorisation ou à l'élimination ?<br/>cochez pour oui (24)", 6),  # 11 → span vertical (11,1)-(11,2)
    ]

    # Ligne 2 – Colonnes finales (cellules vides là où un span vertical est actif)
    header_row2 = [
        "",   # 0  (vide, span vertical depuis ligne 1)
        "",   # 1  (vide, span vertical depuis ligne 1)
        _h("Masse (tonnes)"),
        _h("Volume (optionnel)"),
        "",   # 4  (vide, span vertical depuis ligne 1)
        _h("% Réutilisation (sur site ou hors site) (23)", 6),
        _h("Recyclable"),
        _h("Remblayage, complément de carrière", 6),
        _h("À incinérer avec valorisation énergétique", 6),
        "",   # 9  (vide, span vertical depuis ligne 1)
        "",   # 10 (vide, span vertical depuis ligne 1)
        "",   # 11 (vide, span vertical depuis ligne 1)
    ]

    # ── Données ─────────────────────────────────────────────
    data_rows = []
    for row in rows:
        cat = row.get("categorie", "")
        cat_para = Paragraph(f"<font name='{cell_font}' size='{cell_font_size}'>{cat}</font>", cat_style)
        data_rows.append([
            cat_para,
            row.get("code_dechet", ""),
            _to_num(row.get("masse")),
            _to_num(row.get("volume")),
            _cb(row.get("filiere_exutoires", False)),
            _to_num(row.get("pct_reutilisation")),
            _to_num(row.get("pct_recyclable")),
            _to_num(row.get("pct_remblayage")),
            _to_num(row.get("pct_incineration_valo")),
            _to_num(row.get("pct_incineration_sans_valo")),
            _to_num(row.get("pct_non_valorisable")),
            _cb(row.get("conditions_techniques", False)),
        ])

    data = [header_row0, header_row1, header_row2] + data_rows

    # ── Largeurs ────────────────────────────────────────────
    page_w = landscape(A4)[0] - 1.2 * cm
    col_widths = [
        page_w * 0.13,  # Catégorie
        page_w * 0.06,  # Code déchet
        page_w * 0.06,  # Masse
        page_w * 0.06,  # Volume
        page_w * 0.09,  # Filières (texte long)
        page_w * 0.07,  # Réutilisation
        page_w * 0.06,  # Recyclable
        page_w * 0.07,  # Remblayage
        page_w * 0.07,  # Incinération VE
        page_w * 0.07,  # Incinération sans VE
        page_w * 0.07,  # Non valorisable
        page_w * 0.09,  # Conditions (texte long)
    ]

    table = Table(data, colWidths=col_widths, repeatRows=3)

    # ── Couleurs ────────────────────────────────────────────
    BLUE_DARK = colors.HexColor("#1e3a5f")
    BLUE_MID = colors.HexColor("#bfdbfe")
    PURPLE_LIGHT = colors.HexColor("#c7c8e0")
    GREEN_LIGHT = colors.HexColor("#86efac")
    RED_LIGHT = colors.HexColor("#fca5a5")
    WHITE = colors.HexColor("#ffffff")
    TEXT_DARK = colors.HexColor("#1e3a5f")

    style_commands = [
        # Font globale
        ("FONTNAME", (0, 0), (-1, -1), cell_font),
        ("FONTSIZE", (0, 0), (-1, -1), cell_font_size),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 3), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e3a5f")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e3a5f")),

        # ── Ligne 0 : groupes (bleu foncé, texte blanc) ──
        ("BACKGROUND", (0, 0), (-1, 0), BLUE_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),

        # ── Ligne 1 : sous-groupes ──
        ("BACKGROUND", (0, 1), (1, 1), PURPLE_LIGHT),   # Identification
        ("BACKGROUND", (2, 1), (3, 1), PURPLE_LIGHT),   # Quantité
        ("BACKGROUND", (4, 1), (4, 1), PURPLE_LIGHT),   # Destination
        ("BACKGROUND", (5, 1), (7, 1), GREEN_LIGHT),    # Valorisation matière
        ("BACKGROUND", (8, 1), (8, 1), GREEN_LIGHT),    # Valorisation énergétique
        ("BACKGROUND", (9, 1), (10, 1), RED_LIGHT),     # Élimination
        ("BACKGROUND", (11, 1), (11, 1), PURPLE_LIGHT), # Conditions
        ("TEXTCOLOR", (0, 1), (-1, 1), TEXT_DARK),
        ("TOPPADDING", (0, 1), (-1, 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
        ("LEFTPADDING", (0, 1), (-1, 1), 3),
        ("RIGHTPADDING", (0, 1), (-1, 1), 3),

        # ── Ligne 2 : colonnes finales ──
        ("BACKGROUND", (0, 2), (1, 2), PURPLE_LIGHT),
        ("BACKGROUND", (2, 2), (3, 2), PURPLE_LIGHT),
        ("BACKGROUND", (4, 2), (4, 2), PURPLE_LIGHT),
        ("BACKGROUND", (5, 2), (7, 2), GREEN_LIGHT),
        ("BACKGROUND", (8, 2), (8, 2), GREEN_LIGHT),
        ("BACKGROUND", (9, 2), (10, 2), RED_LIGHT),
        ("BACKGROUND", (11, 2), (11, 2), PURPLE_LIGHT),
        ("TEXTCOLOR", (0, 2), (-1, 2), TEXT_DARK),
        ("TOPPADDING", (0, 2), (-1, 2), 6),
        ("BOTTOMPADDING", (0, 2), (-1, 2), 6),
        ("LEFTPADDING", (0, 2), (-1, 2), 3),
        ("RIGHTPADDING", (0, 2), (-1, 2), 3),

        # ── Cellules de données ──
        ("TOPPADDING", (0, 3), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 3), (-1, -1), 4),
        ("LEFTPADDING", (0, 3), (-1, -1), 3),
        ("RIGHTPADDING", (0, 3), (-1, -1), 3),
    ]

    # ── SPANs ───────────────────────────────────────────────
    # Ligne 0 (groupes)
    style_commands.append(("SPAN", (0, 0), (3, 0)))   # Identification des déchets
    style_commands.append(("SPAN", (5, 0), (8, 0)))   # Valorisation (22)
    style_commands.append(("SPAN", (9, 0), (10, 0)))  # Élimination (22)

    # Ligne 1 (sous-groupes horizontaux)
    style_commands.append(("SPAN", (2, 1), (3, 1)))   # Quantité estimée (20)
    style_commands.append(("SPAN", (5, 1), (7, 1)))   # Valorisation matière

    # SPANs verticaux (ligne 1 → ligne 2) – évite la duplication du texte
    style_commands.append(("SPAN", (0, 1), (0, 2)))   # Catégorie
    style_commands.append(("SPAN", (1, 1), (1, 2)))   # Code déchet
    style_commands.append(("SPAN", (4, 1), (4, 2)))   # Filières et exutoires
    style_commands.append(("SPAN", (9, 1), (9, 2)))   # Incinération sans VE
    style_commands.append(("SPAN", (10, 1), (10, 2))) # Non valorisable
    style_commands.append(("SPAN", (11, 1), (11, 2))) # Conditions techniques

    # Lignes alternées
    for i in range(3, len(data)):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8F9FA")))

    table.setStyle(TableStyle(style_commands))
    story.append(table)
    story.append(Spacer(1, 10))

    # Mention légale
    story.append(
        Paragraph(
            "<i>La somme des colonnes pour une même catégorie de déchets doit être égale à 100 %.</i>",
            styles["Normal"],
        )
    )

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── Multi-table export ─────────────────────────────────────

TABLE_LABELS = {
    "di": "Déchets inertes",
    "dndni": "Déchets non dangereux non inertes (DNDNI)",
    "equipement": "Déchets d'équipements",
    "dd": "Déchets dangereux (DD)",
    "annexe": "Tableau annexe",
}


def generate_multi_table_pdf(project_name: str, tables: Dict[str, List[Dict]]) -> bytes:
    """Génère un PDF avec plusieurs tableaux CERFA (un par section)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=0.6 * cm,
        leftMargin=0.6 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.fontSize = 14
    title_style.spaceAfter = 6

    cell_font = _CELL_FONT
    cell_font_size = _CELL_FONT_SIZE
    header_style = _HEADER_STYLE
    cat_style = _CAT_STYLE

    section_style = ParagraphStyle(
        "section_style",
        fontName=_CELL_FONT,
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#1e3a5f"),
        spaceAfter=8,
        spaceBefore=12,
    )

    story = []
    story.append(Paragraph(f"<b>Caractérisation des déchets</b>", title_style))
    story.append(Paragraph(f"Projet : {project_name}", styles["Normal"]))
    story.append(Spacer(1, 6))

    first_table = True
    for key in ["di", "dndni", "equipement", "dd", "annexe"]:
        rows = tables.get(key)
        if not rows:
            continue

        if not first_table:
            story.append(PageBreak())
        first_table = False

        story.append(Paragraph(f"<b>{TABLE_LABELS.get(key, key)}</b>", section_style))
        story.append(Spacer(1, 4))

        # Reuse the header and data building logic from generate_di_pdf
        # Headers
        def _h(text, color='whitesmoke'):
            return Paragraph(
                f"<font name='{cell_font}' size='7' color='{color}'><b>{text.replace(chr(10), '<br/>')}</b></font>",
                ParagraphStyle("h", fontName=cell_font, fontSize=7, leading=8, alignment=1, wordWrap="LTR")
            )

        header_row0 = [
            _h("Identification des déchets", 8),
            "", "", "",
            _h("Destination (21)", 8),
            _h("Valorisation (22)", 8),
            "", "", "",
            _h("Élimination (22)", 8),
            "",
            _h("Conditions techniques", 8),
        ]

        header_row1 = [
            _h("Catégorie"), _h("Code déchet"),
            _h("Quantité estimée (20)", 7), "",
            _h("Le diagnostic identifie-t-il les filières et exutoires possibles ?<br/>cochez pour oui", 6),
            _h("Valorisation matière"), "", "",
            _h("Valorisation énergétique"),
            _h("% Incinération sans valorisation énergétique", 6),
            _h("% Non valorisable, à enfouir", 6),
            _h("Le diagnostic identifie-t-il les conditions économiques et techniques nécessaires à la valorisation ou à l'élimination ?<br/>cochez pour oui (24)", 6),
        ]

        header_row2 = [
            "", "",
            _h("Masse (tonnes)"), _h("Volume (optionnel)"),
            "",
            _h("% Réutilisation (sur site ou hors site) (23)", 6),
            _h("Recyclable"),
            _h("Remblayage, complément de carrière", 6),
            _h("À incinérer avec valorisation énergétique", 6),
            _h("% Incinération sans valorisation énergétique", 6),
            _h("% Non valorisable, à enfouir", 6),
            _h("Le diagnostic identifie-t-il les conditions économiques et techniques nécessaires à la valorisation ou à l'élimination ?<br/>cochez pour oui (24)", 6),
        ]

        data_rows = []
        for row in rows:
            cat = row.get("categorie", "")
            cat_para = Paragraph(f"<font name='{cell_font}' size='{cell_font_size}'>{cat}</font>", cat_style)
            data_rows.append([
                cat_para,
                row.get("code_dechet", ""),
                _to_num(row.get("masse")),
                _to_num(row.get("volume")),
                _cb(row.get("filiere_exutoires", False)),
                _to_num(row.get("pct_reutilisation")),
                _to_num(row.get("pct_recyclable")),
                _to_num(row.get("pct_remblayage")),
                _to_num(row.get("pct_incineration_valo")),
                _to_num(row.get("pct_incineration_sans_valo")),
                _to_num(row.get("pct_non_valorisable")),
                _cb(row.get("conditions_techniques", False)),
            ])

        data = [header_row0, header_row1, header_row2] + data_rows

        page_w = landscape(A4)[0] - 1.2 * cm
        col_widths = [
            page_w * 0.13, page_w * 0.06, page_w * 0.06, page_w * 0.06,
            page_w * 0.09, page_w * 0.07, page_w * 0.06, page_w * 0.07,
            page_w * 0.07, page_w * 0.07, page_w * 0.07, page_w * 0.09,
        ]

        table = Table(data, colWidths=col_widths, repeatRows=3)

        BLUE_DARK = colors.HexColor("#1e3a5f")
        BLUE_MID = colors.HexColor("#bfdbfe")
        PURPLE_LIGHT = colors.HexColor("#c7c8e0")
        GREEN_LIGHT = colors.HexColor("#86efac")
        RED_LIGHT = colors.HexColor("#fca5a5")
        TEXT_DARK = colors.HexColor("#1e3a5f")

        style_commands = [
            ("FONTNAME", (0, 0), (-1, -1), cell_font),
            ("FONTSIZE", (0, 0), (-1, -1), cell_font_size),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 3), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e3a5f")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e3a5f")),
            ("BACKGROUND", (0, 0), (-1, 0), BLUE_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (1, 1), PURPLE_LIGHT),
            ("BACKGROUND", (2, 1), (3, 1), PURPLE_LIGHT),
            ("BACKGROUND", (4, 1), (4, 1), PURPLE_LIGHT),
            ("BACKGROUND", (5, 1), (7, 1), GREEN_LIGHT),
            ("BACKGROUND", (8, 1), (8, 1), GREEN_LIGHT),
            ("BACKGROUND", (9, 1), (10, 1), RED_LIGHT),
            ("BACKGROUND", (11, 1), (11, 1), PURPLE_LIGHT),
            ("TEXTCOLOR", (0, 1), (-1, 1), TEXT_DARK),
            ("TOPPADDING", (0, 1), (-1, 1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("LEFTPADDING", (0, 1), (-1, 1), 3),
            ("RIGHTPADDING", (0, 1), (-1, 1), 3),
            ("BACKGROUND", (0, 2), (1, 2), PURPLE_LIGHT),
            ("BACKGROUND", (2, 2), (3, 2), PURPLE_LIGHT),
            ("BACKGROUND", (4, 2), (4, 2), PURPLE_LIGHT),
            ("BACKGROUND", (5, 2), (7, 2), GREEN_LIGHT),
            ("BACKGROUND", (8, 2), (8, 2), GREEN_LIGHT),
            ("BACKGROUND", (9, 2), (10, 2), RED_LIGHT),
            ("BACKGROUND", (11, 2), (11, 2), PURPLE_LIGHT),
            ("TEXTCOLOR", (0, 2), (-1, 2), TEXT_DARK),
            ("TOPPADDING", (0, 2), (-1, 2), 6),
            ("BOTTOMPADDING", (0, 2), (-1, 2), 6),
            ("LEFTPADDING", (0, 2), (-1, 2), 3),
            ("RIGHTPADDING", (0, 2), (-1, 2), 3),
            ("TOPPADDING", (0, 3), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 3), (-1, -1), 4),
            ("LEFTPADDING", (0, 3), (-1, -1), 3),
            ("RIGHTPADDING", (0, 3), (-1, -1), 3),
        ]

        style_commands.append(("SPAN", (0, 0), (3, 0)))
        style_commands.append(("SPAN", (5, 0), (8, 0)))
        style_commands.append(("SPAN", (9, 0), (10, 0)))
        style_commands.append(("SPAN", (2, 1), (3, 1)))
        style_commands.append(("SPAN", (5, 1), (7, 1)))
        style_commands.append(("SPAN", (0, 1), (0, 2)))
        style_commands.append(("SPAN", (1, 1), (1, 2)))
        style_commands.append(("SPAN", (4, 1), (4, 2)))
        style_commands.append(("SPAN", (9, 1), (9, 2)))
        style_commands.append(("SPAN", (10, 1), (10, 2)))
        style_commands.append(("SPAN", (11, 1), (11, 2)))

        for i in range(3, len(data)):
            if i % 2 == 0:
                style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8F9FA")))

        table.setStyle(TableStyle(style_commands))
        story.append(table)

    doc.build(story)
    buf.seek(0)
    return buf.read()
