"""
Extracteur spécialisé pour les fenêtres (IfcWindow).

Dimensions extraites :
  - Hauteur : OverallHeight, PropertySets, QuantitySets, géométrie
  - Longueur/Largeur : OverallWidth, PropertySets, QuantitySets
  - Épaisseur : PropertySets (depth), géométrie
"""

import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional

from extractors.common import (
    safe_float, round_val, build_element_dict,
    extract_dimensions_generic,
)


def extract_window_data(element) -> Dict[str, Any]:
    """Point d'entrée : extrait les données complètes d'une fenêtre."""
    dimensions = _extract_window_dimensions(element)
    return build_element_dict(element, "IfcWindow", "Fenêtre", dimensions)


def _extract_window_dimensions(window) -> Dict[str, Optional[float]]:
    """
    Extraction des dimensions d'une fenêtre.
    Priorité : attributs directs → PropertySets → QuantitySets → géométrie.
    """
    hauteur = None
    longueur = None
    epaisseur = None

    # --- SOURCE 1 : Attributs directs IfcWindow ---
    hauteur = safe_float(getattr(window, "OverallHeight", None))
    longueur = safe_float(getattr(window, "OverallWidth", None))

    # --- SOURCE 2 : QuantitySets (Qto_WindowBaseQuantities) ---
    try:
        qsets = ifcopenshell.util.element.get_psets(window, qtos_only=True)
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
                if longueur is None and any(x in k for x in ["width", "length", "longueur", "largeur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["depth", "thickness", "epaisseur", "profondeur"]):
                    epaisseur = v
    except Exception:
        pass

    # --- SOURCE 3 : PropertySets ---
    try:
        psets = ifcopenshell.util.element.get_psets(window, psets_only=True)
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
                if longueur is None and any(x in k for x in ["width", "length", "longueur", "largeur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["depth", "thickness", "epaisseur", "profondeur"]):
                    epaisseur = v
    except Exception:
        pass

    # --- SOURCE 4 : Type (IfcWindowType) ---
    if hauteur is None or longueur is None:
        try:
            win_type = ifcopenshell.util.element.get_type(window)
            if win_type:
                if hauteur is None:
                    hauteur = safe_float(getattr(win_type, "OverallHeight", None))
                if longueur is None:
                    longueur = safe_float(getattr(win_type, "OverallWidth", None))
        except Exception:
            pass

    # --- SOURCE 5 : Géométrie générique (fallback) ---
    if hauteur is None or longueur is None or epaisseur is None:
        generic = extract_dimensions_generic(window)
        hauteur = hauteur or generic.get("hauteur")
        longueur = longueur or generic.get("longueur")
        epaisseur = epaisseur or generic.get("epaisseur")

    return {
        "hauteur": round_val(hauteur),
        "longueur": round_val(longueur),
        "epaisseur": round_val(epaisseur),
    }
