"""
Génère un export PEMD (PDF et CSV) pour la page Extraction.

Tous les composants du bâtiment sont exportés, classifiés selon la
nomenclature CERFA PEMD (Tableau 1 : Liste des catégories et unités
permettant de décrire les PEM).

Champs exportés par composant :
  Macro-catégorie | Catégorie | Type | Floor | Matériel

Résumé affiché en tête :
  Volume total estimé (m³) | Masse totale estimée (kg) | Densité moyenne (kg/m³)
"""

import csv
import io
from collections import defaultdict
from typing import List, Dict, Any, Tuple

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


# ============================================================
# NOMENCLATURE PEMD CERFA — Tableau 1
# Mapping IFC type → (macro_code, macro_label, cat_code, cat_label)
# ============================================================

PEMD_MAPPING: Dict[str, Dict[str, str]] = {
    "Mur": {
        "macro_code":  "5",
        "macro_label": "Cloisonnements - Doublages - Plafonds suspendus - Menuiseries intérieures",
        "cat_code":    "5.1",
        "cat_label":   "Cloisons",
    },
    "Mur rideau": {
        "macro_code":  "6",
        "macro_label": "Façades et menuiseries extérieures",
        "cat_code":    "6.1",
        "cat_label":   "Revêtements, isolations et doublages extérieurs",
    },
    "Dalle": {
        "macro_code":  "3",
        "macro_label": "Superstructures - Maçonneries",
        "cat_code":    "3.1",
        "cat_label":   "Planchers, dalles, balcons",
    },
    "Escalier": {
        "macro_code":  "3",
        "macro_label": "Superstructures - Maçonneries",
        "cat_code":    "3.6",
        "cat_label":   "Escaliers et rampes maçonnées",
    },
    "Porte": {
        "macro_code":  "5",
        "macro_label": "Cloisonnements - Doublages - Plafonds suspendus - Menuiseries intérieures",
        "cat_code":    "5.5",
        "cat_label":   "Menuiseries intérieures",
    },
    "Fenêtre": {
        "macro_code":  "6",
        "macro_label": "Façades et menuiseries extérieures",
        "cat_code":    "6.2",
        "cat_label":   "Portes, fenêtres, fermetures, protections solaires",
    },
    "Toiture": {
        "macro_code":  "4",
        "macro_label": "Couvertures - Étanchéités - Charpentes - Zingueries",
        "cat_code":    "4.1",
        "cat_label":   "Toitures terrasses",
    },
    "Poutre": {
        "macro_code":  "3",
        "macro_label": "Superstructures - Maçonneries",
        "cat_code":    "3.2",
        "cat_label":   "Poutres",
    },
    "Poteau": {
        "macro_code":  "3",
        "macro_label": "Superstructures - Maçonneries",
        "cat_code":    "3.5",
        "cat_label":   "Poteaux",
    },
    "Fondation": {
        "macro_code":  "2",
        "macro_label": "Fondations et infrastructures",
        "cat_code":    "2.1",
        "cat_label":   "Fondations",
    },
}

PEMD_DEFAULT: Dict[str, str] = {
    "macro_code":  "14",
    "macro_label": "Autres",
    "cat_code":    "14.1",
    "cat_label":   "Autres (voir note (4))",
}


# ============================================================
# DENSITÉS MATÉRIAUX (kg/m³) — pour estimation de la masse
# ============================================================

MATERIAL_DENSITIES: Dict[str, float] = {
    "béton":        2400, "beton":        2400, "concrete":     2400,
    "acier":        7850, "steel":        7850, "iron":         7850, "fer":    7850,
    "aluminium":    2700, "aluminum":     2700,
    "bois":          700, "wood":          700, "timber":        700,
    "oak":           750, "chêne":         750, "pin":           600, "pine":   600,
    "lamellé":       600, "glulam":        600, "clt":           600,
    "verre":        2500, "glass":        2500, "vitrage":      2400, "glazing": 2400,
    "brique":       1800, "brick":        1800,
    "plâtre":       1200, "platre":       1200, "gypsum":       1200, "plaster": 1200,
    "pierre":       2600, "stone":        2600, "granite":      2700,
    "marbre":       2800, "marble":       2800,
    "cuivre":       8900, "copper":       8900,
    "zinc":         7200,
    "pvc":          1400, "plastique":    1200, "plastic":      1200,
    "laine":          50, "wool":           50, "rockwool":       35,
    "bitume":       2100, "bitumen":      2100,
    "mortier":      2000, "mortar":       2000,
}

DEFAULT_DENSITY = 2000.0  # kg/m³


def _get_density(materiau: str) -> float:
    if not materiau:
        return DEFAULT_DENSITY
    m = materiau.lower()
    for key, val in MATERIAL_DENSITIES.items():
        if key in m:
            return val
    return DEFAULT_DENSITY


def _get_volume(el: Dict) -> float:
    """Volume m³ : net_volume > volume calculé > 0."""
    v = el.get("net_volume") or el.get("volume")
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# CALCUL RÉSUMÉ
# ============================================================

def _compute_summary(elements: List[Dict]) -> Dict[str, Any]:
    total_volume = 0.0
    total_masse  = 0.0
    mat_acc: Dict[str, Any] = defaultdict(lambda: {"volume": 0.0, "masse": 0.0, "density": 0.0})

    for el in elements:
        v   = _get_volume(el)
        mat = el.get("materiau") or "—"
        d   = _get_density(mat if mat != "—" else "")
        m   = d * v

        total_volume += v
        total_masse  += m
        mat_acc[mat]["volume"]  += v
        mat_acc[mat]["masse"]   += m
        mat_acc[mat]["density"]  = d

    par_materiau: Dict[str, Any] = {}
    for mat, vals in sorted(mat_acc.items(), key=lambda kv: -kv[1]["volume"]):
        par_materiau[mat] = {
            "volume":  round(vals["volume"], 3),
            "masse":   round(vals["masse"] / 1000,  3),
            "density": round(vals["density"] / 1000, 2),
        }

    return {
        "total":        len(elements),
        "volume_total": round(total_volume, 3),
        "masse_totale": round(total_masse / 1000, 3),
        "par_materiau": par_materiau,
    }


# ============================================================
# CONSTRUCTION DES LIGNES GROUPÉES
# ============================================================

def _sort_key(kv: Tuple) -> Tuple:
    """Clé de tri : par numéro de macro-catégorie puis catégorie."""
    key = kv[0]
    macro_code = key[0]  # ex. "3", "14"
    cat_code   = key[2]  # ex. "3.1", "14.1"
    try:
        return (int(macro_code), float(cat_code))
    except (ValueError, TypeError):
        return (999, 999.0)


def _build_rows_grouped(elements: List[Dict]) -> List[List[str]]:
    """
    Regroupe les composants par (catégorie PEMD, matériau).
    Retourne une ligne par groupe avec :
      Macro-catégorie | Catégorie | Type | Matériel | Quantité | Densité utilisée
    """
    groups: Dict[Tuple, List[Dict]] = defaultdict(list)
    for el in elements:
        cat = PEMD_MAPPING.get(el.get("type") or "", PEMD_DEFAULT)
        key = (
            cat["macro_code"],
            cat["macro_label"],
            cat["cat_code"],
            cat["cat_label"],
            el.get("type") or "—",
            el.get("materiau") or "—",
        )
        groups[key].append(el)

    rows = []
    for (macro_code, macro_label, cat_code, cat_label, type_name, materiau), items in sorted(
        groups.items(), key=_sort_key
    ):
        density = _get_density(materiau if materiau != "—" else "")
        rows.append([
            f"{macro_code}. {macro_label}",
            f"{cat_code} — {cat_label}",
            type_name,
            materiau,
            str(len(items)),
        ])
    return rows


# ============================================================
# CSV
# ============================================================

CSV_HEADERS = ["Macro-catégorie", "Catégorie", "Type", "Matériel", "Quantité"]


def generate_extraction_pemd_csv(elements: List[Dict]) -> bytes:
    """Génère le CSV PEMD extraction (UTF-8 + BOM, séparateur ';')."""
    summary = _compute_summary(elements)
    rows    = _build_rows_grouped(elements)

    buf    = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    writer.writerow(["=== RÉSUMÉ DU BÂTIMENT ==="])
    writer.writerow(["Nombre total de composants", summary["total"]])
    writer.writerow([])
    writer.writerow(["Matériau", "Volume estimé (m³)", "Densité (t/m³)", "Masse estimée (t)"])
    for mat, vals in summary["par_materiau"].items():
        writer.writerow([mat, vals["volume"], vals["density"], vals["masse"]])
    writer.writerow(["TOTAL", summary["volume_total"], "", summary["masse_totale"]])
    writer.writerow([])
    writer.writerow(CSV_HEADERS)
    for row in rows:
        writer.writerow(row)

    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


# ============================================================
# PDF
# ============================================================

_BLUE  = colors.HexColor("#1e3a5f")
_GREY  = colors.HexColor("#f3f4f6")
_WHITE = colors.white
_DARK  = colors.HexColor("#374151")
_LBLUE = colors.HexColor("#dbeafe")
_LBLUE2 = colors.HexColor("#eff6ff")


def generate_extraction_pemd_pdf(elements: List[Dict], project_label: str = "") -> bytes:
    """Génère le PDF PEMD extraction en paysage A4."""
    summary = _compute_summary(elements)
    rows    = _build_rows_grouped(elements)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm, leftMargin=1.2 * cm,
        topMargin=1.5 * cm,   bottomMargin=1.2 * cm,
    )

    s_title  = ParagraphStyle("T",   fontSize=13, fontName="Helvetica-Bold",
                               textColor=_WHITE, alignment=TA_CENTER)
    s_sub    = ParagraphStyle("S",   fontSize=8,  fontName="Helvetica",
                               textColor=colors.HexColor("#93c5fd"), alignment=TA_CENTER)
    s_stat   = ParagraphStyle("ST",  fontSize=9,  fontName="Helvetica",
                               textColor=_DARK)
    s_stat_b = ParagraphStyle("STB", fontSize=9,  fontName="Helvetica-Bold",
                               textColor=_DARK)
    s_th     = ParagraphStyle("TH",  fontSize=7.5, fontName="Helvetica-Bold",
                               textColor=_WHITE, alignment=TA_CENTER)
    s_td     = ParagraphStyle("TD",  fontSize=7,  fontName="Helvetica",
                               textColor=_DARK, leading=9)

    story = []

    # --- Bandeau titre ---
    title_text = "Export PEMD — Extraction IFC"
    if project_label:
        title_text += f" — {project_label}"

    cover = Table(
        [[Paragraph(title_text, s_title)],
         [Paragraph(f"{summary['total']} composant(s) exporté(s)", s_sub)]],
        colWidths=[26 * cm],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cover)
    story.append(Spacer(1, 0.4 * cm))

    # --- Bloc résumé par matériau ---
    s_th_s  = ParagraphStyle("THS",  fontSize=7.5, fontName="Helvetica-Bold",
                              textColor=_WHITE, alignment=TA_CENTER)
    s_td_s  = ParagraphStyle("TDS",  fontSize=8,   fontName="Helvetica",
                              textColor=_DARK)
    s_td_r  = ParagraphStyle("TDR",  fontSize=8,   fontName="Helvetica",
                              textColor=_DARK, alignment=TA_RIGHT)
    s_td_b  = ParagraphStyle("TDB",  fontSize=8,   fontName="Helvetica-Bold",
                              textColor=_DARK)
    s_td_rb = ParagraphStyle("TDRB", fontSize=8,   fontName="Helvetica-Bold",
                              textColor=_DARK, alignment=TA_RIGHT)

    sum_headers = ["Matériau", "Volume estimé (m³)", "Densité (kg/m³)", "Masse estimée (kg)"]
    sum_data  = [[Paragraph(h, s_th_s) for h in sum_headers]]
    sum_style = [
        ("BACKGROUND",    (0, 0), (-1, 0), _BLUE),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#bfdbfe")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]
    for ri, (mat, vals) in enumerate(summary["par_materiau"].items(), 1):
        bg = _LBLUE2 if ri % 2 == 0 else _WHITE
        sum_data.append([
            Paragraph(mat,                          s_td_s),
            Paragraph(f"{vals['volume']} m³",      s_td_r),
            Paragraph(f"{vals['density']} t/m³",  s_td_r),
            Paragraph(f"{vals['masse']} t",        s_td_r),
        ])
        sum_style.append(("BACKGROUND", (0, ri), (-1, ri), bg))

    ri_tot = len(summary["par_materiau"]) + 1
    sum_data.append([
        Paragraph("TOTAL",                         s_td_b),
        Paragraph(f"{summary['volume_total']} m³", s_td_rb),
        Paragraph("—",                             s_td_r),
        Paragraph(f"{summary['masse_totale']} t", s_td_rb),
    ])
    sum_style.append(("BACKGROUND", (0, ri_tot), (-1, ri_tot), _LBLUE))

    summary_tbl = Table(sum_data, colWidths=[6 * cm, 5 * cm, 5 * cm, 5 * cm])
    summary_tbl.setStyle(TableStyle(sum_style))
    story.append(summary_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # --- Tableau principal ---
    if not rows:
        story.append(Paragraph("Aucun composant à exporter.", s_td))
        doc.build(story)
        return buf.getvalue()

    page_w = landscape(A4)[0] - 2.4 * cm
    col_widths = [
        page_w * 0.28,  # Macro-catégorie
        page_w * 0.26,  # Catégorie
        page_w * 0.14,  # Type
        page_w * 0.22,  # Matériel
        page_w * 0.10,  # Quantité
    ]

    tdata = [[Paragraph(h, s_th) for h in CSV_HEADERS]]
    style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0), _BLUE),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]

    for ri, row in enumerate(rows, 1):
        bg = _GREY if ri % 2 == 0 else _WHITE
        tdata.append([Paragraph(str(v) if v else "—", s_td) for v in row])
        style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), bg))

    tbl = Table(tdata, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()
