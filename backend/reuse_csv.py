"""
Génère un CSV de diagnostic réemploi (PEM) pour les composants
marqués « à réutiliser » dans le tracker d'un projet.

Conforme à la nomenclature CERFA PEMD (Tableau 1) :
  - Catégories = numéro + nom (ex : « 6.2 Portes, fenêtres, fermetures, protections solaires »)
  - Unités selon « Liste des catégories et unités permettant de décrire les PEM »
  - État ∈ {Neuf, Bon, Moyen, Mauvais}
  - Âge ∈ {Inférieur à 2 ans, Entre 2 et 10 ans, Entre 10 et 50 ans, Supérieur à 50 ans}
  - Type d'assemblage ∈ {Chimique permanent, Chimique réversible, Mécanique, Par gravité}

Règle stricte : pas d'invention. Toute donnée non déductible reste VIDE.
Regroupement BIM : par (catégorie, matériau, dimensions).
"""

import csv
import io
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

from tracker import get_all_components, get_project_ifc, get_project


# ============================================================
# NOMENCLATURE PEMD (CERFA)
# ============================================================

# Mapping IFC type français → (code, libellé officiel, unité retenue)
# Hypothèses par défaut (à ajuster manuellement dans le CSV si besoin) :
#   - Mur          → cloison intérieure (5.1)
#   - Mur rideau   → revêtement extérieur (6.1)
#   - Porte        → menuiserie intérieure (5.5)
#   - Fenêtre      → menuiserie extérieure (6.2)
#   - Dalle        → plancher (3.1)
#   - Escalier     → escalier maçonné (3.6)
PEMD_CATEGORIES = {
    "Mur":        {"code": "5.1", "label": "Cloisons",                                                    "unit": "m²"},
    "Mur rideau": {"code": "6.1", "label": "Revêtements, isolations et doublages extérieurs",            "unit": "m²"},
    "Dalle":      {"code": "3.1", "label": "Planchers, dalles, balcons",                                  "unit": "m²"},
    "Porte":      {"code": "5.5", "label": "Menuiseries intérieures",                                     "unit": "U"},
    "Fenêtre":    {"code": "6.2", "label": "Portes, fenêtres, fermetures, protections solaires",          "unit": "U"},
    "Escalier":   {"code": "3.6", "label": "Escaliers et rampes maçonnées",                               "unit": "U"},
}

# Catégorie de secours (14.1 Autres)
PEMD_DEFAULT = {"code": "14.1", "label": "Autres", "unit": "U"}


# ============================================================
# MAPPING condition tracker → État PEM
# ============================================================

_LEGACY_CONDITION_TO_ETAT = {
    "parfait":  "Neuf",
    "très bon": "Bon",
    "bon":      "Bon",
    "passable": "Moyen",
    "déchet":   "Mauvais",
}


# ============================================================
# ENRICHISSEMENT depuis l'IFC source (si disponible)
# ============================================================

def _parse_ifc_index(ifc_path: str) -> Dict[str, Dict]:
    """Parse l'IFC et retourne un dict indexé par GlobalId."""
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
    """Retire le suffixe '__pN' d'un id stocké pour retrouver le GlobalId IFC."""
    if "__p" in stored_id:
        return stored_id.split("__p")[0]
    return stored_id


# ============================================================
# HELPERS DIMENSIONS / QUANTITÉ / DESCRIPTION
# ============================================================

def _fmt_num(v) -> str:
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
        return f"{f:.1f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


def _dimensions_str(el: Dict) -> str:
    """'H × L × E m (H×L×E)' ou variantes selon les dims dispo."""
    h = _fmt_num(el.get("hauteur"))
    l = _fmt_num(el.get("longueur"))
    e = _fmt_num(el.get("epaisseur"))
    if h and l and e:
        return f"{h} × {l} × {e} m (H×L×E)"
    if h and l:
        return f"{h} × {l} m (H×L)"
    if e:
        return f"ép. {e} m"
    parts = [x for x in [h, l, e] if x]
    return (" × ".join(parts) + " m") if parts else ""


def _quantite(group: List[Dict], unit: str, count: int) -> str:
    """Calcule la quantité disponible pour réemploi (somme du groupe) selon l'unité PEM."""
    if unit == "m²":
        total = 0.0
        valid = False
        for el in group:
            a = el.get("net_area")
            if a is None:
                h, l = el.get("hauteur"), el.get("longueur")
                if h is not None and l is not None:
                    try: a = float(h) * float(l)
                    except (TypeError, ValueError): a = None
            if a is not None:
                try:
                    total += float(a); valid = True
                except (TypeError, ValueError):
                    pass
        if valid:
            return f"{round(total, 1)} m² ({count} éléments)"
        return f"{count} éléments"

    if unit == "ml":
        total = 0.0; valid = False
        for el in group:
            l = el.get("longueur")
            if l is not None:
                try: total += float(l); valid = True
                except (TypeError, ValueError): pass
        if valid:
            return f"{round(total, 2)} ml ({count} éléments)"
        return f"{count} éléments"

    if unit == "m³":
        total = 0.0; valid = False
        for el in group:
            v = el.get("net_volume")
            if v is not None:
                try: total += float(v); valid = True
                except (TypeError, ValueError): pass
        if valid:
            return f"{round(total, 1)} m³ ({count} éléments)"
        return f"{count} éléments"

    # Unitaire
    return f"{count} U"


def _categorie_label(cat: Dict) -> str:
    """'5.5 Menuiseries intérieures'."""
    return f"{cat['code']} {cat['label']}"


def _description(type_name: str, materiau: str, dims: str) -> str:
    """Description précise (col. 6 CERFA) — type + matériau + dims."""
    parts = [type_name or "Composant"]
    if materiau:
        parts.append(f"en {materiau.lower()}")
    if dims:
        parts.append(f"— {dims}")
    return " ".join(parts)


def _localisation(etages: List[str], type_name: str) -> str:
    """Étages distincts + catégorie. La fonction précise n'est pas déductible sans risque."""
    etages_valides = sorted({e for e in etages if e})
    if etages_valides:
        return f"{type_name} — {', '.join(etages_valides)}"
    return type_name or ""


def _join_unique(values: List[str]) -> str:
    """Liste triée des valeurs distinctes non vides. Migre au passage les anciennes
    conditions (déchet/passable/bon/très bon/parfait) vers les nouvelles."""
    out = []
    for v in values:
        if not v:
            continue
        v = _LEGACY_CONDITION_TO_ETAT.get(v, v)
        if v not in out:
            out.append(v)
    return ", ".join(sorted(out))


def _infos_techniques(group: List[Dict], comments: List[str], lifespans: List[int]) -> str:
    """(17) Infos techniques disponibles : agrège ce qui est vérifiable."""
    bits = []
    areas = [float(el["net_area"]) for el in group if el.get("net_area") not in (None, "")]
    if areas:
        bits.append(f"Surface unitaire moy. : {round(sum(areas)/len(areas), 1)} m²")
    vols = [float(el["net_volume"]) for el in group if el.get("net_volume") not in (None, "")]
    if vols:
        bits.append(f"Volume unitaire moy. : {round(sum(vols)/len(vols), 1)} m³")
    valid_ls = [int(x) for x in lifespans if x and int(x) > 0]
    if valid_ls:
        bits.append(f"Durée de vie restante estimée : {min(valid_ls)}–{max(valid_ls)} mois")
    valid_comments = [c.strip() for c in comments if c and c.strip()]
    if valid_comments:
        bits.append("Notes : " + " | ".join(valid_comments[:3]))
    return " ; ".join(bits)


# ============================================================
# GÉNÉRATION DU CSV
# ============================================================

CSV_HEADERS = [
    "(5) Catégorie",
    "(6) Description",
    "(7) Quantité disponible et unité",
    "(8) Dimensions",
    "(9) Type principal d'assemblage",
    "(10) Âge estimé",
    "(11) État de conservation / fonctionnement",
    "(12) Suspect de substances dangereuses",
    "(13) Matériaux constitutifs",
    "(15) Localisation et fonction dans le bâtiment",
    "(16) Conditions techniques et économiques pour le réemploi",
    "(17) Informations techniques disponibles",
    "(18) Précautions de dépose, transport et stockage",
]


def _build_enriched_components(project_id: int) -> List[Dict]:
    """Récupère et enrichit les composants 'à réutiliser' avec les données IFC."""
    components = get_all_components(project_id=project_id, status_filter="à réutiliser")
    ifc_info = get_project_ifc(project_id)
    ifc_index = _parse_ifc_index(ifc_info["path"]) if ifc_info else {}

    enriched: List[Dict] = []
    for comp in components:
        stored_id = comp.get("id", "")
        ifc_id = _ifc_id_from_stored(stored_id)
        ifc_data = ifc_index.get(ifc_id, {})
        enriched.append({
            "type":      comp.get("type") or ifc_data.get("type") or "",
            "materiau":  comp.get("material") or ifc_data.get("materiau") or "",
            "etage":     comp.get("ifc_location") or ifc_data.get("etage") or "",
            "condition":      comp.get("condition"),
            "age_estimated":  comp.get("age_estimated"),
            "comment":        comp.get("comment"),
            "lifespan_months": comp.get("lifespan_months"),
            "hauteur":    comp.get("hauteur") or ifc_data.get("hauteur"),
            "longueur":   comp.get("longueur") or ifc_data.get("longueur"),
            "epaisseur":  comp.get("epaisseur") or ifc_data.get("epaisseur"),
            "net_area":   comp.get("net_area") or ifc_data.get("net_area"),
            "net_volume": comp.get("net_volume") or ifc_data.get("net_volume"),
        })
    return enriched


def _build_groups(enriched: List[Dict]) -> Dict[Tuple, List[Dict]]:
    """Regroupe les composants enrichis par (type, matériau, dimensions)."""
    groups: Dict[Tuple, List[Dict]] = defaultdict(list)
    for el in enriched:
        dims_key = (
            _fmt_num(el["hauteur"]),
            _fmt_num(el["longueur"]),
            _fmt_num(el["epaisseur"]),
        )
        key = (el["type"], el["materiau"], dims_key)
        groups[key].append(el)
    return groups


def get_pemd_grouped_data(project_id: int) -> List[Dict]:
    """
    Retourne les données PEMD groupées pour le projet (composants 'à réutiliser').
    Chaque élément est un dict avec les champs CERFA (5)–(18) prêts à l'export.
    """
    enriched = _build_enriched_components(project_id)
    groups = _build_groups(enriched)

    rows: List[Dict] = []
    for (type_name, materiau, _dims_key), items in sorted(
        groups.items(), key=lambda x: (x[0][0] or "", x[0][1] or "")
    ):
        cat = PEMD_CATEGORIES.get(type_name, PEMD_DEFAULT)
        sample = items[0]
        dims = _dimensions_str(sample)
        qte = _quantite(items, cat["unit"], len(items))

        comments = [it.get("comment") for it in items]
        lifespans = [it.get("lifespan_months") for it in items]

        rows.append({
            "group_key": f"{type_name}|{materiau}|{_dims_key}",
            "categorie": _categorie_label(cat),
            "description": _description(type_name, materiau, dims),
            "quantite": qte,
            "dimensions": dims,
            "assemblage": "",
            "age_estime": _join_unique([it.get("age_estimated") for it in items]),
            "etat": _join_unique([it.get("condition") for it in items]),
            "substances_dangereuses": False,
            "materiaux": materiau or "",
            "localisation": False,
            "conditions_reemploi": False,
            "infos_techniques": False,
            "precautions": False,
            "infos_techniques_text": _infos_techniques(items, comments, lifespans),
            "type_name": type_name,
            "materiau": materiau,
            "count": len(items),
            "unit": cat["unit"],
        })
    return rows


def generate_reuse_csv_from_data(rows: List[Dict]) -> bytes:
    """Génère le CSV (UTF-8 + BOM, séparateur ';') à partir des données fournies."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADERS)

    for row in rows:
        writer.writerow([
            row.get("categorie", ""),
            row.get("description", ""),
            row.get("quantite", ""),
            row.get("dimensions", ""),
            row.get("assemblage", ""),
            row.get("age_estime", ""),
            row.get("etat", ""),
            "Oui" if row.get("substances_dangereuses") else "",
            row.get("materiaux", ""),
            "Oui" if row.get("localisation") else "",
            "Oui" if row.get("conditions_reemploi") else "",
            "Oui" if row.get("infos_techniques") else "",
            "Oui" if row.get("precautions") else "",
        ])

    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def generate_reuse_csv(project_id: int) -> bytes:
    """Génère le CSV (UTF-8 + BOM, séparateur ';')."""
    project = get_project(project_id)
    if not project:
        raise ValueError(f"Projet {project_id} introuvable.")
    rows = get_pemd_grouped_data(project_id)
    return generate_reuse_csv_from_data(rows)
