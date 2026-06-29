"""
Extracteur spécialisé pour les portes (IfcDoor).

Dimensions extraites :
  - Hauteur : BaseQuantities (Height), attribut OverallHeight, PropertySets
  - Longueur (largeur) : BaseQuantities (Width), attribut OverallWidth, PropertySets
  - Épaisseur : BaseQuantities (Depth), PropertySets, géométrie
"""

import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional

from extractors.common import (
    safe_float, round_val, build_element_dict,
    extract_dimensions_generic,
)


def extract_door_data(element) -> Dict[str, Any]:
    """Point d'entrée : extrait les données complètes d'une porte."""
    dimensions = _extract_door_dimensions(element)
    # Pas d'épaisseur ni de volume pour les portes
    dimensions["epaisseur"] = None
    data = build_element_dict(element, "IfcDoor", "Porte", dimensions)
    data["nb_battants"] = _extract_nb_battants(element)
    return data


def _extract_nb_battants(door) -> Optional[int]:
    """
    Extrait le nombre de battants d'une porte depuis Name et ObjectType.
    """
    try:
        text = ""

        if door.Name:
            text += door.Name.lower()

        if door.ObjectType:
            text += door.ObjectType.lower()

        if "double" in text:
            return 2
        if "single" in text or "simple" in text:
            return 1

    except:
        pass

    return None


def _extract_door_dimensions(door) -> Dict[str, Optional[float]]:
    """
    Extraction des dimensions d'une porte.
    Priorité : BaseQuantities → attributs directs → PropertySets → type → géométrie.
    """
    hauteur = None
    longueur = None
    epaisseur = None

    # --- SOURCE 1 : QuantitySets (Qto_DoorBaseQuantities) ---
    try:
        qsets = ifcopenshell.util.element.get_psets(door, qtos_only=True)
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
                if longueur is None and any(x in k for x in ["width", "largeur", "longueur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["depth", "thickness", "epaisseur", "profondeur"]):
                    epaisseur = v
    except Exception:
        pass

    # --- SOURCE 2 : Attributs directs IfcDoor ---
    if hauteur is None:
        hauteur = safe_float(getattr(door, "OverallHeight", None))
    if longueur is None:
        longueur = safe_float(getattr(door, "OverallWidth", None))

    # --- SOURCE 3 : PropertySets ---
    try:
        psets = ifcopenshell.util.element.get_psets(door, psets_only=True)
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
                if longueur is None and any(x in k for x in ["width", "largeur", "longueur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["depth", "thickness", "epaisseur", "profondeur"]):
                    epaisseur = v
    except Exception:
        pass

    # --- SOURCE 4 : Type (IfcDoorType / IfcDoorStyle) ---
    if hauteur is None or longueur is None:
        try:
            door_type = ifcopenshell.util.element.get_type(door)
            if door_type:
                # Attributs directs du type
                if hauteur is None:
                    hauteur = safe_float(getattr(door_type, "OverallHeight", None))
                if longueur is None:
                    longueur = safe_float(getattr(door_type, "OverallWidth", None))

                # QuantitySets du type
                try:
                    qsets_type = ifcopenshell.util.element.get_psets(door_type, qtos_only=True)
                    for qset_name, qset_data in qsets_type.items():
                        if not isinstance(qset_data, dict):
                            continue
                        for key, value in qset_data.items():
                            k = key.lower()
                            v = safe_float(value)
                            if v is None:
                                continue
                            if hauteur is None and "height" in k:
                                hauteur = v
                            if longueur is None and "width" in k:
                                longueur = v
                            if epaisseur is None and any(x in k for x in ["depth", "thickness"]):
                                epaisseur = v
                except Exception:
                    pass
        except Exception:
            pass

    # --- SOURCE 5 : Géométrie générique (fallback) ---
    if hauteur is None or longueur is None or epaisseur is None:
        generic = extract_dimensions_generic(door)
        hauteur = hauteur or generic.get("hauteur")
        longueur = longueur or generic.get("longueur")
        epaisseur = epaisseur or generic.get("epaisseur")

    # Conversion mm → m si les valeurs semblent être en millimètres (> 10)
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
