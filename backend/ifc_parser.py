"""
Orchestrateur principal d'extraction IFC.
Délègue l'extraction de chaque type de composant à son module spécialisé
dans le package extractors/.

Structure :
  extractors/
    __init__.py        — registre EXTRACTOR_MAP
    common.py          — helpers partagés (matériau, étage, géométrie)
    walls.py           — extraction murs (IfcWall)
    windows.py         — extraction fenêtres (IfcWindow)
    slabs.py           — extraction dalles (IfcSlab)
    stairs.py          — extraction escaliers (IfcStair)
    curtain_walls.py   — extraction murs rideaux (IfcCurtainWall)
"""

import os
import ifcopenshell
from typing import List, Dict, Any

from extractors import EXTRACTOR_MAP


def _is_sub_element(element) -> bool:
    """Vérifie si un élément est un sous-élément décomposé d'un autre (ex: dalle dans un escalier)."""
    try:
        for rel in (getattr(element, "Decomposes", None) or []):
            parent = getattr(rel, "RelatingObject", None)
            if parent and not parent.is_a(element.is_a()):
                return True
    except Exception:
        pass
    return False


# ============================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================

def parse_ifc_file(file_path: str) -> Dict[str, Any]:
    """
    Parse un fichier IFC et extrait les éléments pertinents.
    Chaque type IFC est traité par son extracteur spécialisé.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Fichier non trouvé : {file_path}")

    ifc_file = ifcopenshell.open(file_path)

    elements: List[Dict[str, Any]] = []
    messages: List[str] = []

    for ifc_type, (french_name, extractor_fn) in EXTRACTOR_MAP.items():
        found_elements = ifc_file.by_type(ifc_type)

        if not found_elements:
            messages.append(f"Aucun(e) {french_name.lower()} trouvé(e) dans ce fichier IFC")
            continue

        for elem in found_elements:
            # Exclure les sous-éléments décomposés (ex: dalles palier dans un escalier)
            if _is_sub_element(elem):
                continue
            element_data = extractor_fn(elem)
            elements.append(element_data)

    return {
        "elements": elements,
        "messages": messages,
    }
