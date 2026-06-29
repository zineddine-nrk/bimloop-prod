"""
Génération du CSV et des données groupées « Déchets inertes (DI) » selon le formulaire CERFA PEMD.

Périmètre :
- On ne compte QUE les éléments dont le matériau correspond à l'une des
  catégories DI réglementaires (béton, briques, tuiles, verre, etc.).
- On ne compte QUE les éléments dont le statut tracker est « à recycler »
  ou « à réutiliser » (les autres ne partent pas en DI).

Colonnes (structure CERFA complète) :
  - Catégorie
  - Code déchet
  - Quantité estimée → Masse (tonnes), Volume (m³, optionnel)
  - Destination (21) : filières et exutoires identifiés (checkbox)
  - Valorisation matière (22) : % Réutilisation, % Recyclable, % Remblayage
  - Valorisation énergétique : % À incinérer avec valorisation énergétique
  - Élimination (22) : % Incinération sans valorisation, % Non valorisable
  - Conditions techniques (24) : checkbox
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import List, Dict, Optional

from tracker import get_all_components, get_project_ifc, get_project


# ============================================================
# CATÉGORIES DI (ordre + libellés du CERFA)
# ============================================================
# Chaque catégorie a :
#   - "label"    : libellé exact du formulaire
#   - "keywords" : mots-clés cherchés dans le matériau (lowercase, accents tolérés)
#   - "density"  : kg/m³ par défaut (utilisé si le volume IFC est connu)

DI_CATEGORIES: List[Dict] = [
    {
        "label": "Béton",
        "keywords": ["béton", "beton", "concrete"],
        "density": 2400,
    },
    {
        "label": "Briques",
        "keywords": ["brique", "brick"],
        "density": 1800,
    },
    {
        "label": "Tuiles et céramiques",
        "keywords": ["tuile", "céramique", "ceramique", "ceramic", "carrelage", "faïence", "faience"],
        "density": 2000,
    },
    {
        "label": "Mélanges de béton, tuiles et céramique ne contenant pas de substances dangereuses",
        "keywords": [],
        "density": 2200,
    },
    {
        "label": "Verre (sans cadre ou montant de fenêtres)",
        "keywords": ["verre", "glass"],
        "density": 2500,
    },
    {
        "label": "Verre (triés)",
        "keywords": [],
        "density": 2500,
    },
    {
        "label": "Mélange bitumineux ne contenant pas de goudron",
        "keywords": ["bitume", "bitumen", "asphalte", "asphalt", "enrobé", "enrobe"],
        "density": 2300,
    },
    {
        "label": "Terres et cailloux ne contenant pas de substance dangereuse",
        "keywords": ["cailloux", "gravier", "gravel"],
        "density": 1800,
    },
    {
        "label": "Terres et pierres",
        "keywords": ["terre", "pierre", "stone", "soil"],
        "density": 1700,
    },
    {
        "label": "Déchets de matériaux à base de fibre et de verre",
        "keywords": ["laine de verre", "fibre de verre", "glass wool", "fiberglass"],
        "density": 100,
    },
    {
        "label": "Emballage en verre",
        "keywords": ["emballage verre", "glass packaging"],
        "density": 2500,
    },
]

# Headers CERFA complets
DI_CSV_HEADERS = [
    "Catégorie",
    "Code déchet",
    "Masse estimée (tonnes)",
    "Volume estimé (m³)",
    "Filières et exutoires identifiés",
    "% Réutilisation (sur site ou hors site)",
    "% Recyclable",
    "% Remblayage / comblement de carrière",
    "% Incinération avec valorisation énergétique",
    "% Incinération sans valorisation énergétique",
    "% Non valorisable, à enfouir",
    "Conditions techniques identifiées",
]


# ============================================================
# HELPERS
# ============================================================

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _classify(material: str) -> Optional[int]:
    """Retourne l'index de la catégorie DI correspondant au matériau, ou None."""
    m = _norm(material)
    if not m:
        return None
    # Spécifiques d'abord
    priority_order = [9, 10, 4, 6, 7, 8, 2, 1, 0, 3]
    for i in priority_order:
        for kw in DI_CATEGORIES[i]["keywords"]:
            if kw in m:
                return i
    return None


def _safe_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _compute_volume(ifc_data: Dict) -> Optional[float]:
    """Volume en m³ : net_volume direct si dispo, sinon h*l*e."""
    nv = _safe_float(ifc_data.get("net_volume"))
    if nv:
        return nv
    h = _safe_float(ifc_data.get("hauteur"))
    l = _safe_float(ifc_data.get("longueur"))
    e = _safe_float(ifc_data.get("epaisseur"))
    if h and l and e:
        return h * l * e
    na = _safe_float(ifc_data.get("net_area"))
    if na and e:
        return na * e
    return None


def _ifc_id_from_stored(stored_id: str) -> str:
    if "__p" in stored_id:
        return stored_id.split("__p")[0]
    return stored_id


def _fmt(v: float, decimals: int = 1) -> str:
    if v is None:
        return ""
    return f"{round(v, decimals):.{decimals}f}".rstrip("0").rstrip(".") or "0"


# ============================================================
# DONNÉES GROUPÉES (pour le modal DI)
# ============================================================

def get_di_grouped_data(project_id: int) -> List[Dict]:
    """Retourne les données DI groupées par catégorie pour le projet."""
    if get_project(project_id) is None:
        raise ValueError(f"Projet {project_id} introuvable.")

    all_comps = get_all_components(project_id=project_id)

    # Enrichissement IFC
    ifc_info = get_project_ifc(project_id)
    ifc_index: Dict[str, Dict] = {}
    if ifc_info:
        try:
            from ifc_parser import parse_ifc_file
            data = parse_ifc_file(ifc_info["path"])
            elements = data.get("elements", []) if isinstance(data, dict) else data
            for el in elements:
                gid = el.get("id")
                if gid:
                    ifc_index[gid] = el
        except Exception:
            ifc_index = {}

    # Agrégation par catégorie DI
    per_cat: Dict[int, Dict] = defaultdict(
        lambda: {
            "n_total": 0, "vol_total": 0.0, "mass_total": 0.0,
            "n_reuse": 0, "vol_reuse": 0.0, "mass_reuse": 0.0,
            "n_recyc": 0, "vol_recyc": 0.0, "mass_recyc": 0.0,
        }
    )

    for comp in all_comps:
        cat_idx = _classify(comp.get("material") or "")
        if cat_idx is None:
            continue

        ifc_data = ifc_index.get(_ifc_id_from_stored(comp.get("id", "")), {})
        merged = {
            "hauteur":    comp.get("hauteur")    or ifc_data.get("hauteur"),
            "longueur":   comp.get("longueur")   or ifc_data.get("longueur"),
            "epaisseur":  comp.get("epaisseur")  or ifc_data.get("epaisseur"),
            "net_area":   comp.get("net_area")   or ifc_data.get("net_area"),
            "net_volume": comp.get("net_volume") or ifc_data.get("net_volume"),
        }
        vol = _compute_volume(merged) or 0.0
        density = DI_CATEGORIES[cat_idx]["density"]
        mass_t = (vol * density) / 1000.0

        bucket = per_cat[cat_idx]
        bucket["n_total"]    += 1
        bucket["vol_total"]  += vol
        bucket["mass_total"] += mass_t

        status = (comp.get("status") or "").strip().lower()
        if status == "à réutiliser":
            bucket["n_reuse"]    += 1
            bucket["vol_reuse"]  += vol
            bucket["mass_reuse"] += mass_t
        elif status == "à recycler":
            bucket["n_recyc"]    += 1
            bucket["vol_recyc"]  += vol
            bucket["mass_recyc"] += mass_t

    # Construction des rows (une par catégorie, y compris vides)
    rows = []
    for idx, cat in enumerate(DI_CATEGORIES):
        agg = per_cat.get(idx)
        if agg and agg["n_total"] > 0:
            mass = agg["mass_total"]
            vol = agg["vol_total"]

            if agg["mass_total"] > 0:
                pct_reuse = agg["mass_reuse"] / agg["mass_total"] * 100
                pct_recyc = agg["mass_recyc"] / agg["mass_total"] * 100
            elif agg["vol_total"] > 0:
                pct_reuse = agg["vol_reuse"] / agg["vol_total"] * 100
                pct_recyc = agg["vol_recyc"] / agg["vol_total"] * 100
            else:
                pct_reuse = agg["n_reuse"] / agg["n_total"] * 100
                pct_recyc = agg["n_recyc"] / agg["n_total"] * 100

            rows.append({
                "idx": idx,
                "categorie": cat["label"],
                "code_dechet": "",
                "masse": _fmt(mass) if mass > 0 else "",
                "volume": _fmt(vol) if vol > 0 else "",
                "filiere_exutoires": False,
                "pct_reutilisation": f"{pct_reuse:.1f}" if pct_reuse > 0 else "",
                "pct_recyclable": f"{pct_recyc:.1f}" if pct_recyc > 0 else "",
                "pct_remblayage": "",
                "pct_incineration_valo": "",
                "pct_incineration_sans_valo": "",
                "pct_non_valorisable": "",
                "conditions_techniques": False,
            })
        else:
            rows.append({
                "idx": idx,
                "categorie": cat["label"],
                "code_dechet": "",
                "masse": "",
                "volume": "",
                "filiere_exutoires": False,
                "pct_reutilisation": "",
                "pct_recyclable": "",
                "pct_remblayage": "",
                "pct_incineration_valo": "",
                "pct_incineration_sans_valo": "",
                "pct_non_valorisable": "",
                "conditions_techniques": False,
            })
    return rows


# ============================================================
# EXPORT CSV
# ============================================================

def generate_di_csv_from_data(rows: List[Dict]) -> bytes:
    """Génère le CSV DI à partir des données fournies."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(DI_CSV_HEADERS)

    for row in rows:
        writer.writerow([
            row.get("categorie", ""),
            row.get("code_dechet", ""),
            row.get("masse", ""),
            row.get("volume", ""),
            "Oui" if row.get("filiere_exutoires") else "",
            row.get("pct_reutilisation", ""),
            row.get("pct_recyclable", ""),
            row.get("pct_remblayage", ""),
            row.get("pct_incineration_valo", ""),
            row.get("pct_incineration_sans_valo", ""),
            row.get("pct_non_valorisable", ""),
            "Oui" if row.get("conditions_techniques") else "",
        ])

    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def generate_di_csv(project_id: int) -> bytes:
    """Construit le CSV DI pour un projet (rétrocompatibilité)."""
    rows = get_di_grouped_data(project_id)
    return generate_di_csv_from_data(rows)


# ============================================================
# EXPORT CSV MULTI-TABLEAUX
# ============================================================

TABLE_LABELS = {
    "di": "Déchets inertes",
    "dndni": "Déchets non dangereux non inertes (DNDNI)",
    "equipement": "Déchets d'équipements",
    "dd": "Déchets dangereux (DD)",
    "annexe": "Tableau annexe",
}


def generate_multi_table_csv(tables: Dict[str, List[Dict]]) -> bytes:
    """Génère un CSV avec plusieurs sections (une par tableau)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    first = True
    for key in ["di", "dndni", "equipement", "dd", "annexe"]:
        rows = tables.get(key)
        if not rows:
            continue
        if not first:
            writer.writerow([])
        writer.writerow([TABLE_LABELS.get(key, key)])
        writer.writerow(DI_CSV_HEADERS)
        for row in rows:
            writer.writerow([
                row.get("categorie", ""),
                row.get("code_dechet", ""),
                row.get("masse", ""),
                row.get("volume", ""),
                "Oui" if row.get("filiere_exutoires") else "",
                row.get("pct_reutilisation", ""),
                row.get("pct_recyclable", ""),
                row.get("pct_remblayage", ""),
                row.get("pct_incineration_valo", ""),
                row.get("pct_incineration_sans_valo", ""),
                row.get("pct_non_valorisable", ""),
                "Oui" if row.get("conditions_techniques") else "",
            ])
        first = False
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
