"""
Exporte un fichier IFC enrichi avec les statuts de tracking depuis la DB SQLite.
Chaque élément reçoit un IfcPropertySet 'Pset_IFCAnalyzer_Status' contenant
son statut actuel (in_building, démonté, transporté, stocké, réutilisé, etc.).
"""

import io
import os
import ifcopenshell
from ifcopenshell import guid
from typing import Dict, Optional

from tracker import init_db, get_components_meta_by_ids


# Nom du PropertySet injecté sur chaque composant tracké.
PSET_NAME = "Pset_IFCAnalyzer_Status"


def export_ifc_with_statuses(input_path: str,
                             output_path: Optional[str] = None,
                             project_id: Optional[int] = None) -> bytes:
    """
    Lit un fichier IFC, injecte les statuts ET métadonnées du tracker (condition,
    commentaire, durée de vie, dernière note) via un PropertySet, et retourne les
    bytes du fichier modifié.

    Si project_id est fourni, n'utilise que les composants de ce projet.
    Si output_path est fourni, sauvegarde aussi sur disque.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Fichier IFC non trouvé : {input_path}")

    # Ouvrir le fichier IFC
    ifc_file = ifcopenshell.open(input_path)

    # Récupérer tous les GlobalIds du fichier
    elements_with_guid = []
    for entity in ifc_file:
        try:
            gid = getattr(entity, "GlobalId", None)
            if gid:
                elements_with_guid.append((entity, gid))
        except Exception:
            continue

    if not elements_with_guid:
        return _save_to_bytes(ifc_file)

    # Récupérer les métadonnées complètes depuis la DB
    guids = [g for _, g in elements_with_guid]
    meta_by_id = get_components_meta_by_ids(guids, project_id=project_id)

    if not meta_by_id:
        return _save_to_bytes(ifc_file)

    # Créer le OwnerHistory (nécessaire pour les nouvelles entités)
    owner_history = _get_or_create_owner_history(ifc_file)

    # OPTIMISATION : indexer en UNE passe les PropertySets "Pset_IFCAnalyzer_Status"
    # déjà existants, mappés par element_id. Avant, on rescannait TOUTES les
    # IfcRelDefinesByProperties pour chaque composant → O(N × R) prohibitif sur un
    # IFC à 6000 composants. Désormais O(R + N).
    existing_pset_by_element_id = {}
    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        try:
            pset = rel.RelatingPropertyDefinition
            if getattr(pset, "Name", None) != PSET_NAME:
                continue
            for obj in rel.RelatedObjects or []:
                existing_pset_by_element_id[obj.id()] = pset
        except Exception:
            continue

    enriched = 0
    for element, gid in elements_with_guid:
        meta = meta_by_id.get(gid)
        if not meta:
            continue
        existing = existing_pset_by_element_id.get(element.id())
        _attach_status_pset(ifc_file, element, meta, owner_history, existing)
        enriched += 1

    buf = _save_to_bytes(ifc_file)
    if output_path:
        ifc_file.write(output_path)
    return buf


def _get_or_create_owner_history(ifc_file):
    """Récupère ou crée un OwnerHistory pour les nouvelles entités."""
    histories = ifc_file.by_type("IfcOwnerHistory")
    if histories:
        return histories[0]

    # Créer un OwnerHistory minimal
    person = ifc_file.create_entity("IfcPerson", Identification="IFCAnalyzer")
    org = ifc_file.create_entity("IfcOrganization", Name="IFCAnalyzer")
    p_and_o = ifc_file.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=org)
    app = ifc_file.create_entity("IfcApplication",
        ApplicationDeveloper=org,
        Version="1.0",
        ApplicationFullName="IFC Analyzer",
        ApplicationIdentifier="IFCAnalyzer"
    )
    owner_history = ifc_file.create_entity("IfcOwnerHistory",
        OwningUser=p_and_o,
        OwningApplication=app,
        ChangeAction="ADDED",
        CreationDate=0
    )
    return owner_history


def _build_properties(ifc_file, meta: dict):
    """Construit la liste des IfcPropertySingleValue à partir des métadonnées.
    Les champs vides/None sont remplacés par '-' (les types IFC string n'acceptent
    pas toujours les chaînes vides selon le schéma)."""
    def _safe_str(v):
        s = "" if v is None else str(v).strip()
        return s if s else "-"

    status   = _safe_str(meta.get("status"))
    condition = _safe_str(meta.get("condition"))
    comment  = _safe_str(meta.get("comment"))
    last_note = _safe_str(meta.get("last_note"))
    last_update = _safe_str((meta.get("updated_at") or "")[:19])
    try:
        lifespan = int(meta.get("lifespan_months") or 0)
    except (TypeError, ValueError):
        lifespan = 0

    props_def = [
        ("CurrentStatus",   "Statut actuel du composant",                   "IfcText",    status),
        ("Condition",       "État physique (déchet/passable/bon/très bon/parfait)", "IfcLabel", condition),
        ("Comment",         "Commentaire libre",                            "IfcText",    comment),
        ("LifespanMonths",  "Durée de vie restante en mois (0 = inconnu)",  "IfcInteger", lifespan),
        ("LastStatusNote",  "Dernière note (lieu / raison de stockage)",    "IfcText",    last_note),
        ("LastUpdate",      "Date de dernière mise à jour (UTC)",           "IfcText",    last_update),
    ]
    out = []
    for name, desc, ifc_type, value in props_def:
        try:
            out.append(ifc_file.create_entity(
                "IfcPropertySingleValue",
                Name=name,
                Description=desc,
                NominalValue=ifc_file.create_entity(ifc_type, value),
            ))
        except Exception:
            # En cas de souci sur un champ, on l'ignore plutôt que de casser tout l'export
            continue
    return out


def _attach_status_pset(ifc_file, element, meta: dict, owner_history, existing_pset=None):
    """Attache (ou met à jour) le PropertySet 'Pset_IFCAnalyzer_Status'.

    `existing_pset` est récupéré en O(1) par l'appelant via le dict
    `existing_pset_by_element_id` construit en une seule passe — bien plus
    rapide que de rescanner toutes les IfcRelDefinesByProperties à chaque
    composant.
    """
    new_props = _build_properties(ifc_file, meta)

    if existing_pset is not None:
        # On remplace toutes les propriétés par les nouvelles
        existing_pset.HasProperties = new_props
        return

    pset = ifc_file.create_entity(
        "IfcPropertySet",
        GlobalId=guid.new(),
        OwnerHistory=owner_history,
        Name=PSET_NAME,
        Description="Métadonnées de tracking IFC Analyzer",
        HasProperties=new_props,
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=guid.new(),
        OwnerHistory=owner_history,
        RelatedObjects=[element],
        RelatingPropertyDefinition=pset,
    )


def _save_to_bytes(ifc_file) -> bytes:
    """Sauvegarde un fichier IFC en mémoire et retourne les bytes.
    ifcopenshell.write() n'accepte qu'un path → on utilise to_string() ou un tmp.
    """
    try:
        return ifc_file.to_string().encode("utf-8")
    except Exception:
        import tempfile, os as _os
        tmp = tempfile.NamedTemporaryFile(suffix=".ifc", delete=False)
        tmp.close()
        try:
            ifc_file.write(tmp.name)
            with open(tmp.name, "rb") as f:
                return f.read()
        finally:
            if _os.path.exists(tmp.name):
                _os.remove(tmp.name)
