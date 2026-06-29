"""
Extracteur spécialisé pour les escaliers (IfcStair).

Données extraites depuis BaseQuantities :
  - NumberOfRiser : nombre de contremarches
  - NumberOfTreads : nombre de marches
  - TreadLength : longueur de marche
  - RiserHeight : hauteur de contremarche
"""

import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional

from extractors.common import (
    safe_float, round_val, build_element_dict,
)


def extract_stair_data(element) -> Dict[str, Any]:
    """Point d'entrée : extrait les données complètes d'un escalier."""
    stair_data = _extract_stair_quantities(element)
    dimensions = {
        "hauteur": None,
        "longueur": None,
        "epaisseur": None,
    }
    data = build_element_dict(element, "IfcStair", "Escalier", dimensions)
    data["number_of_riser"] = stair_data["number_of_riser"]
    data["number_of_treads"] = stair_data["number_of_treads"]
    data["tread_length"] = stair_data["tread_length"]
    data["riser_height"] = stair_data["riser_height"]
    return data


def _extract_stair_quantities(stair) -> Dict[str, Optional[float]]:
    """
    Extraction de NumberOfRiser, NumberOfTreads, TreadLength, RiserHeight
    depuis Pset_StairCommon.
    """
    number_of_riser = None
    number_of_treads = None
    tread_length = None
    riser_height = None

    try:
        psets = ifcopenshell.util.element.get_psets(stair, psets_only=True)
        for pset_name, pset_data in psets.items():
            if not isinstance(pset_data, dict):
                continue
            for key, value in pset_data.items():
                k = key.lower()
                v = safe_float(value)
                if v is None:
                    continue
                if number_of_riser is None and "numberofriser" in k:
                    number_of_riser = int(v)
                if number_of_treads is None and "numberoftread" in k:
                    number_of_treads = int(v)
                if tread_length is None and "treadlength" in k:
                    tread_length = v
                if riser_height is None and "riserheight" in k:
                    riser_height = v
    except Exception:
        pass

    # Conversion mm → m pour tread_length et riser_height
    if tread_length is not None and tread_length > 10:
        tread_length = tread_length / 1000.0
    if riser_height is not None and riser_height > 10:
        riser_height = riser_height / 1000.0

    return {
        "number_of_riser": number_of_riser,
        "number_of_treads": number_of_treads,
        "tread_length": round_val(tread_length),
        "riser_height": round_val(riser_height),
    }
