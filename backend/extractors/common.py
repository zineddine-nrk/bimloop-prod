"""
Fonctions utilitaires partagées entre tous les extracteurs.
Contient : helpers numériques, extraction matériau, extraction étage,
parsing géométrique récursif.
"""

import math
import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Optional, Tuple, List


# ============================================================
# HELPERS NUMÉRIQUES
# ============================================================

def safe_float(value) -> Optional[float]:
    """Convertit une valeur en float > 0, ou retourne None."""
    try:
        result = float(value)
        if result > 0:
            return result
        return None
    except (ValueError, TypeError):
        return None


def round_val(value: Optional[float]) -> Optional[float]:
    """Arrondit une valeur à 3 décimales, ou retourne None."""
    if value is not None and value > 0:
        return round(value, 3)
    return None


# ============================================================
# EXTRACTION DE L'ÉTAGE (IfcBuildingStorey)
# ============================================================

def extract_storey(element) -> Optional[str]:
    """
    Extrait le nom de l'étage (IfcBuildingStorey) auquel appartient un élément.
    Remonte la hiérarchie spatiale via 3 méthodes en cascade.
    """
    # Méthode 1 : ContainedInStructure (relation directe)
    try:
        rels = getattr(element, "ContainedInStructure", None)
        if rels:
            for rel in rels:
                structure = getattr(rel, "RelatingStructure", None)
                if structure and structure.is_a("IfcBuildingStorey"):
                    return getattr(structure, "Name", None) or "Étage inconnu"
    except Exception:
        pass

    # Méthode 2 : Decomposes (pour les éléments agrégés)
    try:
        decomposes = getattr(element, "Decomposes", None)
        if decomposes:
            for rel in decomposes:
                parent = getattr(rel, "RelatingObject", None)
                if parent:
                    parent_storey = extract_storey(parent)
                    if parent_storey:
                        return parent_storey
    except Exception:
        pass

    # Méthode 3 : ObjectPlacement → PlacementRelTo
    try:
        placement = getattr(element, "ObjectPlacement", None)
        if placement:
            rel_placement = getattr(placement, "PlacementRelTo", None)
            if rel_placement:
                for inv in getattr(rel_placement, "PlacesObject", []):
                    if inv.is_a("IfcBuildingStorey"):
                        return getattr(inv, "Name", None) or "Étage inconnu"
    except Exception:
        pass

    return None


# ============================================================
# EXTRACTION DU MATÉRIAU
# ============================================================

def extract_material(element) -> str:
    """
    Extrait le matériau d'un élément IFC.
    Gère : matériau simple, MaterialLayerSet, MaterialLayerSetUsage,
    MaterialConstituentSet, MaterialProfileSet, et PropertySets.
    """
    try:
        material = ifcopenshell.util.element.get_material(element)
        if material:
            # Cas d'un matériau simple
            if hasattr(material, "Name") and material.Name:
                return material.Name

            # Cas d'un MaterialLayerSet
            if hasattr(material, "MaterialLayers"):
                layer_names = []
                for layer in material.MaterialLayers:
                    if hasattr(layer, "Material") and layer.Material and hasattr(layer.Material, "Name"):
                        layer_names.append(layer.Material.Name)
                if layer_names:
                    return ", ".join(layer_names)

            # Cas d'un MaterialLayerSetUsage
            if hasattr(material, "ForLayerSet"):
                layer_set = material.ForLayerSet
                if hasattr(layer_set, "MaterialLayers"):
                    layer_names = []
                    for layer in layer_set.MaterialLayers:
                        if hasattr(layer, "Material") and layer.Material and hasattr(layer.Material, "Name"):
                            layer_names.append(layer.Material.Name)
                    if layer_names:
                        return ", ".join(layer_names)

            # Cas d'un MaterialConstituentSet
            if hasattr(material, "MaterialConstituents"):
                constituent_names = []
                for constituent in material.MaterialConstituents:
                    if hasattr(constituent, "Material") and constituent.Material and hasattr(constituent.Material, "Name"):
                        constituent_names.append(constituent.Material.Name)
                if constituent_names:
                    return ", ".join(constituent_names)

            # Cas d'un MaterialProfileSet
            if hasattr(material, "MaterialProfiles"):
                profile_names = []
                for profile in material.MaterialProfiles:
                    if hasattr(profile, "Material") and profile.Material and hasattr(profile.Material, "Name"):
                        profile_names.append(profile.Material.Name)
                if profile_names:
                    return ", ".join(profile_names)

    except Exception:
        pass

    # Méthode 2 : chercher dans les property sets
    try:
        psets = ifcopenshell.util.element.get_psets(element)
        for pset_name, pset_data in psets.items():
            if isinstance(pset_data, dict):
                for key, value in pset_data.items():
                    if "material" in key.lower() or "materiau" in key.lower():
                        if value and isinstance(value, str):
                            return value
    except Exception:
        pass

    return "Inconnu"


# ============================================================
# EXTRACTION GÉNÉRIQUE DES DIMENSIONS (PropertySets + QuantitySets + Géométrie)
# ============================================================

def extract_dimensions_generic(element) -> Dict[str, Optional[float]]:
    """
    Extraction générique des dimensions pour tout type d'élément.
    Cherche dans PropertySets, QuantitySets et géométrie.
    """
    hauteur = None
    longueur = None
    epaisseur = None

    # PropertySets
    try:
        psets = ifcopenshell.util.element.get_psets(element, psets_only=True)
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
                if longueur is None and any(x in k for x in ["length", "longueur", "width", "largeur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["thickness", "epaisseur", "depth", "profondeur"]):
                    epaisseur = v
    except Exception:
        pass

    # QuantitySets
    try:
        qsets = ifcopenshell.util.element.get_psets(element, qtos_only=True)
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
                if longueur is None and any(x in k for x in ["length", "longueur", "width", "largeur"]):
                    longueur = v
                if epaisseur is None and any(x in k for x in ["thickness", "epaisseur", "depth", "profondeur"]):
                    epaisseur = v
    except Exception:
        pass

    # Géométrie (extrusion)
    try:
        rep = getattr(element, "Representation", None)
        if rep:
            for r in rep.Representations:
                r_id = (getattr(r, "RepresentationIdentifier", "") or "").lower()
                if r_id == "body":
                    for item in r.Items:
                        h, e = parse_body_item_recursive(item)
                        if h and hauteur is None:
                            hauteur = h
                        if e and epaisseur is None:
                            epaisseur = e
    except Exception:
        pass

    return {
        "hauteur": round_val(hauteur),
        "longueur": round_val(longueur),
        "epaisseur": round_val(epaisseur),
    }


# ============================================================
# PARSING GÉOMÉTRIQUE RÉCURSIF
# ============================================================

def parse_body_item_recursive(item) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse récursif d'un élément Body pour extraire hauteur et épaisseur.
    Gère : IfcExtrudedAreaSolid, IfcBooleanClippingResult,
    IfcBooleanResult, IfcMappedItem.
    """
    hauteur = None
    epaisseur = None

    try:
        # Cas 1 : IfcExtrudedAreaSolid
        if item.is_a("IfcExtrudedAreaSolid"):
            depth = safe_float(getattr(item, "Depth", None))
            if depth:
                hauteur = depth
            profile = getattr(item, "SweptArea", None)
            if profile:
                epaisseur = extract_profile_thickness(profile)

        # Cas 2 : IfcBooleanClippingResult / IfcBooleanResult
        elif item.is_a("IfcBooleanResult"):
            first_op = getattr(item, "FirstOperand", None)
            if first_op:
                h, e = parse_body_item_recursive(first_op)
                if h: hauteur = h
                if e: epaisseur = e

        # Cas 3 : IfcMappedItem
        elif item.is_a("IfcMappedItem"):
            source = getattr(item, "MappingSource", None)
            if source:
                mapped_rep = getattr(source, "MappedRepresentation", None)
                if mapped_rep and hasattr(mapped_rep, "Items"):
                    for sub_item in mapped_rep.Items:
                        h, e = parse_body_item_recursive(sub_item)
                        if h and hauteur is None: hauteur = h
                        if e and epaisseur is None: epaisseur = e

        # Cas 4 : IfcFacetedBrep / IfcShellBasedSurfaceModel → bounding box
        elif item.is_a("IfcFacetedBrep") or item.is_a("IfcShellBasedSurfaceModel"):
            dims = bounding_box_from_brep(item)
            if dims:
                sorted_dims = sorted(dims)
                epaisseur = sorted_dims[0]
                hauteur = sorted_dims[1] if len(sorted_dims) > 1 else None

    except Exception:
        pass

    return hauteur, epaisseur


def extract_profile_thickness(profile) -> Optional[float]:
    """
    Extrait l'épaisseur depuis un profil de section.
    Gère : IfcRectangleProfileDef, IfcArbitraryClosedProfileDef,
    IfcCircleProfileDef, IfcIShapeProfileDef, etc.
    """
    try:
        if profile.is_a("IfcRectangleProfileDef"):
            x = safe_float(getattr(profile, "XDim", None))
            y = safe_float(getattr(profile, "YDim", None))
            if x and y:
                return min(x, y)
            return x or y

        if profile.is_a("IfcArbitraryClosedProfileDef"):
            outer_curve = getattr(profile, "OuterCurve", None)
            if outer_curve:
                bbox = bounding_box_from_curve(outer_curve)
                if bbox:
                    return min(bbox)

        if profile.is_a("IfcCircleProfileDef"):
            r = safe_float(getattr(profile, "Radius", None))
            if r:
                return r * 2

        for attr_name in ["WebThickness", "WallThickness", "FlangeThickness", "WallNominalSize"]:
            val = safe_float(getattr(profile, attr_name, None))
            if val:
                return val

    except Exception:
        pass

    return None


def calc_curve_length(curve_item) -> Optional[float]:
    """
    Calcule la longueur d'une courbe IFC.
    Gère : IfcPolyline, IfcTrimmedCurve, IfcCompositeCurve,
    IfcIndexedPolyCurve, IfcLine.
    """
    try:
        # IfcPolyline
        if curve_item.is_a("IfcPolyline"):
            points = curve_item.Points
            if len(points) >= 2:
                total = 0.0
                for i in range(len(points) - 1):
                    c1 = points[i].Coordinates
                    c2 = points[i + 1].Coordinates
                    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
                    total += dist
                return total if total > 0 else None

        # IfcTrimmedCurve
        if curve_item.is_a("IfcTrimmedCurve"):
            basis = getattr(curve_item, "BasisCurve", None)
            trim1 = getattr(curve_item, "Trim1", None)
            trim2 = getattr(curve_item, "Trim2", None)
            if trim1 and trim2:
                p1 = _extract_trim_point(trim1)
                p2 = _extract_trim_point(trim2)
                if p1 and p2:
                    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
            if basis and basis.is_a("IfcLine"):
                return calc_curve_length(basis)

        # IfcCompositeCurve
        if curve_item.is_a("IfcCompositeCurve"):
            segments = getattr(curve_item, "Segments", [])
            total = 0.0
            for seg in segments:
                parent_curve = getattr(seg, "ParentCurve", None)
                if parent_curve:
                    seg_len = calc_curve_length(parent_curve)
                    if seg_len:
                        total += seg_len
            return total if total > 0 else None

        # IfcIndexedPolyCurve (IFC4)
        if curve_item.is_a("IfcIndexedPolyCurve"):
            points_list = getattr(curve_item, "Points", None)
            if points_list:
                coord_list = getattr(points_list, "CoordList", None)
                if coord_list and len(coord_list) >= 2:
                    total = 0.0
                    for i in range(len(coord_list) - 1):
                        c1 = coord_list[i]
                        c2 = coord_list[i + 1]
                        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
                        total += dist
                    return total if total > 0 else None

    except Exception:
        pass

    return None


def _extract_trim_point(trim_values) -> Optional[list]:
    """Extrait un point 3D depuis les valeurs de trim d'une IfcTrimmedCurve."""
    try:
        for val in trim_values:
            if hasattr(val, "Coordinates"):
                return list(val.Coordinates)
            if hasattr(val, "is_a") and val.is_a("IfcCartesianPoint"):
                return list(val.Coordinates)
    except Exception:
        pass
    return None


def bounding_box_from_curve(curve) -> Optional[Tuple[float, float]]:
    """Calcule le bounding box 2D d'une courbe. Retourne (dim_x, dim_y)."""
    points = []
    try:
        if curve.is_a("IfcPolyline"):
            for pt in curve.Points:
                points.append(pt.Coordinates)
        elif curve.is_a("IfcIndexedPolyCurve"):
            pts = getattr(curve, "Points", None)
            if pts:
                coord_list = getattr(pts, "CoordList", None)
                if coord_list:
                    points = list(coord_list)
    except Exception:
        pass

    if len(points) < 2:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)

    if dx > 0 and dy > 0:
        return (dx, dy)
    return None


def bounding_box_from_brep(item) -> Optional[List[float]]:
    """Calcule les dimensions du bounding box 3D d'un IfcFacetedBrep."""
    points = []
    try:
        if item.is_a("IfcFacetedBrep"):
            outer = getattr(item, "Outer", None)
            if outer:
                for face in (getattr(outer, "CfsFaces", None) or []):
                    for bound in (getattr(face, "Bounds", None) or []):
                        loop = getattr(bound, "Bound", None)
                        if loop and hasattr(loop, "Polygon"):
                            for pt in loop.Polygon:
                                points.append(pt.Coordinates)
    except Exception:
        pass

    if len(points) < 3:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points if len(p) > 2]

    dims = []
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    if dx > 0: dims.append(dx)
    if dy > 0: dims.append(dy)
    if zs:
        dz = max(zs) - min(zs)
        if dz > 0: dims.append(dz)

    return dims if dims else None


# ============================================================
# CONSTRUCTION DU DICT ÉLÉMENT (format commun)
# ============================================================

def build_element_dict(element, ifc_type: str, french_name: str,
                       dimensions: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """
    Construit le dictionnaire standard d'un élément analysé.
    Utilisé par tous les extracteurs pour garantir un format uniforme.
    """
    name = getattr(element, "Name", None) or "Sans nom"
    global_id = getattr(element, "GlobalId", None) or "N/A"
    material = extract_material(element)
    etage = extract_storey(element)

    return {
        "id": global_id,
        "nom": name,
        "type_ifc": ifc_type,
        "type": french_name,
        "etage": etage,
        "hauteur": dimensions.get("hauteur"),
        "longueur": dimensions.get("longueur"),
        "epaisseur": dimensions.get("epaisseur"),
        "materiau": material,
    }
