"""
Extracteur spécialisé pour les murs rideaux (IfcCurtainWall).

Dimensions extraites :
  - Hauteur, Longueur : QuantitySets, PropertySets, géométrie, sous-éléments
  - Épaisseur : PropertySets, profils, panneaux
"""

import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional

from extractors.common import (
    safe_float, round_val, build_element_dict,
    extract_dimensions_generic,
)


def extract_curtain_wall_data(element) -> Dict[str, Any]:
    """Point d'entrée : extrait les données complètes d'un mur rideau."""
    dimensions = _extract_curtain_wall_dimensions(element)
    return build_element_dict(element, "IfcCurtainWall", "Mur rideau", dimensions)


def _extract_curtain_wall_dimensions(cw) -> Dict[str, Optional[float]]:
    """
    Extraction des dimensions d'un mur rideau.
    Combine QuantitySets, PropertySets, sous-éléments et géométrie.
    """
    hauteur = None
    longueur = None
    epaisseur = None

    # --- SOURCE 1 : QuantitySets ---
    try:
        qsets = ifcopenshell.util.element.get_psets(cw, qtos_only=True)
        for qset_name, qset_data in qsets.items():
            if not isinstance(qset_data, dict):
                continue
            for key, value in qset_data.items():
                k = key.lower()
                v = safe_float(value)
                if v is None:
                    continue
                if hauteur is None and any(x in k for x in ["height", "hauteur"]):
                    hauteur = v
                if longueur is None and any(x in k for x in ["length", "width", "longueur", "largeur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["depth", "thickness", "epaisseur"]):
                    epaisseur = v
    except Exception:
        pass

    # --- SOURCE 2 : PropertySets ---
    try:
        psets = ifcopenshell.util.element.get_psets(cw, psets_only=True)
        for pset_name, pset_data in psets.items():
            if not isinstance(pset_data, dict):
                continue
            for key, value in pset_data.items():
                k = key.lower()
                v = safe_float(value)
                if v is None:
                    continue
                if hauteur is None and any(x in k for x in ["height", "hauteur"]):
                    hauteur = v
                if longueur is None and any(x in k for x in ["length", "width", "longueur", "largeur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["depth", "thickness", "epaisseur"]):
                    epaisseur = v
    except Exception:
        pass

    # --- SOURCE 3 : Sous-éléments (panneaux IfcPlate, meneaux IfcMember) ---
    if hauteur is None or longueur is None:
        try:
            decomposed = getattr(cw, "IsDecomposedBy", None)
            if decomposed:
                max_h = 0
                max_l = 0
                for rel in decomposed:
                    for sub in (getattr(rel, "RelatedObjects", None) or []):
                        sub_dims = extract_dimensions_generic(sub)
                        sh = sub_dims.get("hauteur") or 0
                        sl = sub_dims.get("longueur") or 0
                        se = sub_dims.get("epaisseur")
                        if sh > max_h:
                            max_h = sh
                        if sl > max_l:
                            max_l = sl
                        if epaisseur is None and se:
                            epaisseur = se
                if hauteur is None and max_h > 0:
                    hauteur = max_h
                if longueur is None and max_l > 0:
                    longueur = max_l
        except Exception:
            pass

    # --- SOURCE 4 : Géométrie générique (fallback) ---
    if hauteur is None or longueur is None or epaisseur is None:
        generic = extract_dimensions_generic(cw)
        hauteur = hauteur or generic.get("hauteur")
        longueur = longueur or generic.get("longueur")
        epaisseur = epaisseur or generic.get("epaisseur")

    return {
        "hauteur": round_val(hauteur),
        "longueur": round_val(longueur),
        "epaisseur": round_val(epaisseur),
    }
