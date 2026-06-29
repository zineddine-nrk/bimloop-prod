"""
Génère un PDF BTP Match pour les composants marqués « à réutiliser »
dans le tracker d'un projet.

Colonnes exportées (8 champs) :
  Catégorie | Description | Quantité | Dimensions |
  Âge estimé | État | Matériel | Localisation

Même logique de regroupement BIM que reuse_csv.py :
  regroupement par (type, matériau, dimensions arrondies).
"""

import io
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from tracker import get_all_components, get_project_ifc, get_project


# ============================================================
# NOMENCLATURE PEMD (CERFA) — identique à reuse_csv.py
# ============================================================

PEMD_CATEGORIES = {
    "Mur":        {"code": "5.1",  "label": "Cloisons",                                                "unit": "m²"},
    "Mur rideau": {"code": "6.1",  "label": "Revêtements, isolations et doublages extérieurs",         "unit": "m²"},
    "Dalle":      {"code": "3.1",  "label": "Planchers, dalles, balcons",                               "unit": "m²"},
    "Porte":      {"code": "5.5",  "label": "Menuiseries intérieures",                                  "unit": "U"},
    "Fenêtre":    {"code": "6.2",  "label": "Portes, fenêtres, fermetures, protections solaires",       "unit": "U"},
    "Escalier":   {"code": "3.6",  "label": "Escaliers et rampes maçonnées",                            "unit": "U"},
}
PEMD_DEFAULT = {"code": "14.1", "label": "Autres", "unit": "U"}

_LEGACY_CONDITION_TO_ETAT = {
    "parfait":  "Neuf",
    "très bon": "Bon",
    "bon":      "Bon",
    "passable": "Moyen",
    "déchet":   "Mauvais",
}


# ============================================================
# HELPERS (identiques à reuse_csv.py)
# ============================================================

def _parse_ifc_index(ifc_path: str) -> Dict[str, Dict]:
    try:
        from ifc_parser import parse_ifc_file
        data = parse_ifc_file(ifc_path)
        elements = data.get("elements", []) if isinstance(data, dict) else data
    except Exception:
        return {}
    idx = {}
    for el in elements:
        gid = el.get("id")
        if gid:
            idx[gid] = el
    return idx


def _ifc_id_from_stored(stored_id: str) -> str:
    if "__p" in stored_id:
        return stored_id.split("__p")[0]
    return stored_id


def _fmt_num(v) -> str:
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
        return f"{f:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


def _dimensions_str(el: Dict) -> str:
    h = _fmt_num(el.get("hauteur"))
    l = _fmt_num(el.get("longueur"))
    e = _fmt_num(el.get("epaisseur"))
    if h and l and e:
        return f"{h} × {l} × {e} m"
    if h and l:
        return f"{h} × {l} m"
    if e:
        return f"ép. {e} m"
    parts = [x for x in [h, l, e] if x]
    return (" × ".join(parts) + " m") if parts else "—"


def _quantite(group: List[Dict], unit: str, count: int) -> str:
    if unit == "m²":
        total = 0.0; valid = False
        for el in group:
            a = el.get("net_area")
            if a is None:
                h, l = el.get("hauteur"), el.get("longueur")
                if h is not None and l is not None:
                    try: a = float(h) * float(l)
                    except (TypeError, ValueError): a = None
            if a is not None:
                try: total += float(a); valid = True
                except (TypeError, ValueError): pass
        if valid:
            return f"{round(total, 2)} m² ({count} él.)"
        return f"{count} éléments"
    if unit == "ml":
        total = 0.0; valid = False
        for el in group:
            l = el.get("longueur")
            if l is not None:
                try: total += float(l); valid = True
                except (TypeError, ValueError): pass
        if valid:
            return f"{round(total, 2)} ml ({count} él.)"
        return f"{count} éléments"
    if unit == "m³":
        total = 0.0; valid = False
        for el in group:
            v = el.get("net_volume")
            if v is not None:
                try: total += float(v); valid = True
                except (TypeError, ValueError): pass
        if valid:
            return f"{round(total, 3)} m³ ({count} él.)"
        return f"{count} éléments"
    return f"{count} U"


def _categorie_label(cat: Dict) -> str:
    return f"{cat['code']} {cat['label']}"


def _description(type_name: str, materiau: str, dims: str) -> str:
    parts = [type_name or "Composant"]
    if materiau:
        parts.append(f"en {materiau.lower()}")
    if dims and dims != "—":
        parts.append(f"— {dims}")
    return " ".join(parts)


def _localisation(etages: List[str], type_name: str) -> str:
    etages_valides = sorted({e for e in etages if e})
    if etages_valides:
        return f"{type_name} — {', '.join(etages_valides)}"
    return type_name or "—"


def _join_unique(values: List[str]) -> str:
    out = []
    for v in values:
        if not v:
            continue
        v = _LEGACY_CONDITION_TO_ETAT.get(v, v)
        if v not in out:
            out.append(v)
    return ", ".join(sorted(out)) if out else "—"


# ============================================================
# PALETTE PDF
# ============================================================

_BLUE  = colors.HexColor("#1e3a5f")
_LBLUE = colors.HexColor("#dbeafe")
_GREY  = colors.HexColor("#f3f4f6")
_WHITE = colors.white
_DARK  = colors.HexColor("#374151")

PDF_HEADERS = [
    "Catégorie",
    "Description",
    "Quantité",
    "Dimensions",
    "Âge estimé",
    "État",
    "Matériel",
]


# ============================================================
# GÉNÉRATION DU PDF
# ============================================================

def generate_btp_match_pdf(project_id: int) -> bytes:
    """Génère le PDF BTP Match pour les composants « à réutiliser »."""
    project = get_project(project_id)
    if not project:
        raise ValueError(f"Projet {project_id} introuvable.")

    components = get_all_components(project_id=project_id, status_filter="à réutiliser")

    ifc_info = get_project_ifc(project_id)
    ifc_index = _parse_ifc_index(ifc_info["path"]) if ifc_info else {}

    enriched: List[Dict] = []
    for comp in components:
        stored_id = comp.get("id", "")
        ifc_id = _ifc_id_from_stored(stored_id)
        ifc_data = ifc_index.get(ifc_id, {})
        enriched.append({
            "type":           comp.get("type") or ifc_data.get("type") or "",
            "materiau":       comp.get("material") or ifc_data.get("materiau") or "",
            "condition":      comp.get("condition"),
            "age_estimated":  comp.get("age_estimated"),
            "hauteur":        comp.get("hauteur") or ifc_data.get("hauteur"),
            "longueur":       comp.get("longueur") or ifc_data.get("longueur"),
            "epaisseur":      comp.get("epaisseur") or ifc_data.get("epaisseur"),
            "net_area":       comp.get("net_area") or ifc_data.get("net_area"),
            "net_volume":     comp.get("net_volume") or ifc_data.get("net_volume"),
        })

    groups: Dict[Tuple, List[Dict]] = defaultdict(list)
    for el in enriched:
        dims_key = (
            _fmt_num(el["hauteur"]),
            _fmt_num(el["longueur"]),
            _fmt_num(el["epaisseur"]),
        )
        key = (el["type"], el["materiau"], dims_key)
        groups[key].append(el)

    rows = []
    for (type_name, materiau, _dims_key), items in sorted(
        groups.items(), key=lambda x: (x[0][0] or "", x[0][1] or "")
    ):
        cat = PEMD_CATEGORIES.get(type_name, PEMD_DEFAULT)
        sample = items[0]
        dims = _dimensions_str(sample)
        qte  = _quantite(items, cat["unit"], len(items))

        rows.append([
            _categorie_label(cat),
            _description(type_name, materiau, dims),
            qte,
            dims,
            _join_unique([it.get("age_estimated") for it in items]),
            _join_unique([it.get("condition") for it in items]),
            materiau or "—",
        ])

    return _build_pdf(project.get("name", f"Projet {project_id}"), rows)


def _build_pdf(project_name: str, rows: List[List[str]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm, leftMargin=1.2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.2 * cm,
    )

    s_title = ParagraphStyle("T",  fontSize=13, fontName="Helvetica-Bold",
                              textColor=_WHITE, alignment=TA_CENTER)
    s_sub   = ParagraphStyle("S",  fontSize=8,  fontName="Helvetica",
                              textColor=colors.HexColor("#93c5fd"), alignment=TA_CENTER)
    s_th    = ParagraphStyle("TH", fontSize=7.5, fontName="Helvetica-Bold",
                              textColor=_WHITE, alignment=TA_CENTER)
    s_td    = ParagraphStyle("TD", fontSize=7,  fontName="Helvetica",
                              textColor=_DARK, leading=9)

    story = []

    cover = Table(
        [[Paragraph(f"BTP Match — {project_name}", s_title)],
         [Paragraph(f"Composants disponibles pour réemploi — {len(rows)} groupe(s)", s_sub)]],
        colWidths=[26 * cm],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cover)
    story.append(Spacer(1, 0.5 * cm))

    if not rows:
        story.append(Paragraph("Aucun composant « à réutiliser » trouvé pour ce projet.", s_td))
        doc.build(story)
        return buf.getvalue()

    n_cols = len(PDF_HEADERS)
    page_w = landscape(A4)[0] - 2.4 * cm
    col_widths = [
        page_w * 0.16,  # Catégorie
        page_w * 0.22,  # Description
        page_w * 0.12,  # Quantité
        page_w * 0.14,  # Dimensions
        page_w * 0.14,  # Âge estimé
        page_w * 0.10,  # État
        page_w * 0.12,  # Matériel
    ]

    tdata = [[Paragraph(h, s_th) for h in PDF_HEADERS]]
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
        tdata.append([Paragraph(str(v) if v is not None else "—", s_td) for v in row])
        style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), bg))

    tbl = Table(tdata, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()
