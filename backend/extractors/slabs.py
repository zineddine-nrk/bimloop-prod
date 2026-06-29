"""
Extracteur spécialisé pour les dalles (IfcSlab).

Dimensions extraites depuis BaseQuantities :
  - Width : épaisseur de la dalle
  - NetArea : surface nette
  - NetVolume : volume net
"""

import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional

from extractors.common import (
    safe_float, round_val, build_element_dict,
)


def extract_slab_data(element) -> Dict[str, Any]:
    """Point d'entrée : extrait les données complètes d'une dalle."""
    slab_data = _extract_slab_quantities(element)
    dimensions = {
        "hauteur": None,
        "longueur": None,
        "epaisseur": slab_data["width"],
    }
    data = build_element_dict(element, "IfcSlab", "Dalle", dimensions)
    data["net_area"] = slab_data["net_area"]
    data["net_volume"] = slab_data["net_volume"]
    return data


def _extract_slab_quantities(slab) -> Dict[str, Optional[float]]:
    """
    Extraction de Width, NetArea et NetVolume depuis BaseQuantities.
    """
    width = None
    net_area = None
    net_volume = None

    try:
        qsets = ifcopenshell.util.element.get_psets(slab, qtos_only=True)
        for qset_name, qset_data in qsets.items():
            if not isinstance(qset_data, dict):
                continue
            for key, value in qset_data.items():
                k = key.lower()
                v = safe_float(value)
                if v is None:
                    continue
                if width is None and "width" in k:
                    width = v
                if net_area is None and "netarea" in k:
                    net_area = v
                if net_volume is None and "netvolume" in k:
                    net_volume = v
    except Exception:
        pass

    # Conversion mm → m pour width
    if width is not None and width > 10:
        width = width / 1000.0

    return {
        "width": round_val(width),
        "net_area": round_val(net_area),
        "net_volume": round_val(net_volume),
    }
