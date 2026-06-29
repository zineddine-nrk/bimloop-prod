"""
Extracteur spécialisé pour les murs (IfcWall / IfcWallStandardCase).

Dimensions extraites depuis BaseQuantities :
  - Hauteur : Height
  - Longueur : Length
  - Épaisseur : Width
"""

import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional

from extractors.common import (
    safe_float, round_val, build_element_dict,
)


def extract_wall_data(element) -> Dict[str, Any]:
    """Point d'entrée : extrait les données complètes d'un mur."""
    dimensions = _extract_wall_dimensions(element)
    return build_element_dict(element, "IfcWall", "Mur", dimensions)


def _extract_wall_dimensions(wall) -> Dict[str, Optional[float]]:
    """
    Extraction des dimensions d'un mur depuis BaseQuantities.
    Cherche Height, Length, Width dans les QuantitySets.
    """
    hauteur = None
    longueur = None
    epaisseur = None

    try:
        qsets = ifcopenshell.util.element.get_psets(wall, qtos_only=True)
        for qset_name, qset_data in qsets.items():
            if not isinstance(qset_data, dict):
                continue
            for key, value in qset_data.items():
                k = key.lower()
                v = safe_float(value)
                if v is None:
                    continue
                if hauteur is None and "height" in k:
                    hauteur = v
                if longueur is None and "length" in k:
                    longueur = v
                if epaisseur is None and "width" in k:
                    epaisseur = v
    except Exception:
        pass

    # Conversion mm → m
    if hauteur is not None and hauteur > 10:
        hauteur = hauteur / 1000.0
    if longueur is not None and longueur > 10:
        longueur = longueur / 1000.0
    if epaisseur is not None and epaisseur > 10:
        epaisseur = epaisseur / 1000.0

    return {
        "hauteur": round_val(hauteur),
        "longueur": round_val(longueur),
        "epaisseur": round_val(epaisseur),
    }
