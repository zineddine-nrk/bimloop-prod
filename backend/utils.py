"""
Module utilitaire pour les calculs de durabilité et les statistiques.
Logique métier réaliste basée sur les pratiques BTP et économie circulaire.

Références :
- Recyclabilité : basée sur les filières de valorisation existantes en BTP
- Réutilisation : basée sur la démontabilité et le potentiel de réemploi
- Scores : échelle 0 à 1 reflétant le potentiel réel en fin de vie
"""

from typing import List, Dict, Any, Optional


# ============================================================
# RECYCLABILITÉ — Règles métier réalistes (matériau → statut + score)
# ============================================================
# Score 0.0 à 1.0 basé sur :
#   - Existence d'une filière de recyclage mature
#   - Taux de recyclage effectif dans le BTP
#   - Qualité du matériau recyclé (downcycling vs upcycling)
# ============================================================
MATERIAUX_RECYCLABILITE = {
    # --- Métaux : filière très mature, recyclage quasi infini ---
    "acier":      {"statut": "OUI", "score": 0.95, "detail": "Recyclable via fonderie, filière mature"},
    "steel":      {"statut": "OUI", "score": 0.95, "detail": "Recyclable via fonderie, filière mature"},
    "iron":       {"statut": "OUI", "score": 0.90, "detail": "Recyclable via fonderie"},
    "fer":        {"statut": "OUI", "score": 0.90, "detail": "Recyclable via fonderie"},
    "aluminium":  {"statut": "OUI", "score": 0.92, "detail": "Recyclable à l'infini, très valorisé"},
    "aluminum":   {"statut": "OUI", "score": 0.92, "detail": "Recyclable à l'infini, très valorisé"},
    "cuivre":     {"statut": "OUI", "score": 0.93, "detail": "Recyclable, haute valeur marchande"},
    "copper":     {"statut": "OUI", "score": 0.93, "detail": "Recyclable, haute valeur marchande"},
    "zinc":       {"statut": "OUI", "score": 0.85, "detail": "Recyclable via fonderie"},
    "inox":       {"statut": "OUI", "score": 0.93, "detail": "Recyclable, acier inoxydable valorisé"},
    "stainless":  {"statut": "OUI", "score": 0.93, "detail": "Recyclable, acier inoxydable valorisé"},

    # --- Béton : recyclable en granulats (downcycling) ---
    "béton":      {"statut": "OUI", "score": 0.60, "detail": "Recyclable en granulats, downcycling"},
    "beton":      {"statut": "OUI", "score": 0.60, "detail": "Recyclable en granulats, downcycling"},
    "concrete":   {"statut": "OUI", "score": 0.60, "detail": "Recyclable en granulats, downcycling"},
    "ciment":     {"statut": "OUI", "score": 0.45, "detail": "Partiellement recyclable en granulats"},
    "cement":     {"statut": "OUI", "score": 0.45, "detail": "Partiellement recyclable en granulats"},
    "mortier":    {"statut": "OUI", "score": 0.40, "detail": "Recyclable en granulats fins"},
    "mortar":     {"statut": "OUI", "score": 0.40, "detail": "Recyclable en granulats fins"},

    # --- Bois : recyclable et valorisable ---
    "bois":       {"statut": "OUI", "score": 0.80, "detail": "Recyclable, réutilisable ou valorisation énergétique"},
    "wood":       {"statut": "OUI", "score": 0.80, "detail": "Recyclable, réutilisable ou valorisation énergétique"},
    "timber":     {"statut": "OUI", "score": 0.80, "detail": "Recyclable, réutilisable ou valorisation énergétique"},
    "oak":        {"statut": "OUI", "score": 0.85, "detail": "Bois noble, fort potentiel de réemploi"},
    "chêne":      {"statut": "OUI", "score": 0.85, "detail": "Bois noble, fort potentiel de réemploi"},
    "pin":        {"statut": "OUI", "score": 0.75, "detail": "Recyclable, valorisation énergétique"},
    "pine":       {"statut": "OUI", "score": 0.75, "detail": "Recyclable, valorisation énergétique"},
    "lamellé":    {"statut": "OUI", "score": 0.70, "detail": "Recyclable, bois d'ingénierie"},
    "glulam":     {"statut": "OUI", "score": 0.70, "detail": "Recyclable, bois d'ingénierie"},
    "clt":        {"statut": "OUI", "score": 0.70, "detail": "Recyclable, bois lamellé croisé"},

    # --- Verre : recyclable mais filière variable ---
    "verre":      {"statut": "OUI", "score": 0.70, "detail": "Recyclable via calcin, filière existante"},
    "glass":      {"statut": "OUI", "score": 0.70, "detail": "Recyclable via calcin, filière existante"},
    "vitrage":    {"statut": "OUI", "score": 0.65, "detail": "Recyclable, nécessite démontage soigné"},
    "glazing":    {"statut": "OUI", "score": 0.65, "detail": "Recyclable, nécessite démontage soigné"},

    # --- Pierre naturelle : réutilisable plutôt que recyclable ---
    "pierre":     {"statut": "OUI", "score": 0.75, "detail": "Réutilisable ou concassage en granulats"},
    "stone":      {"statut": "OUI", "score": 0.75, "detail": "Réutilisable ou concassage en granulats"},
    "granite":    {"statut": "OUI", "score": 0.80, "detail": "Pierre durable, fort potentiel de réemploi"},
    "marbre":     {"statut": "OUI", "score": 0.80, "detail": "Pierre noble, fort potentiel de réemploi"},
    "marble":     {"statut": "OUI", "score": 0.80, "detail": "Pierre noble, fort potentiel de réemploi"},
    "brique":     {"statut": "OUI", "score": 0.65, "detail": "Recyclable en granulats ou réemploi"},
    "brick":      {"statut": "OUI", "score": 0.65, "detail": "Recyclable en granulats ou réemploi"},

    # --- Plâtre : recyclable mais filière limitée ---
    "plâtre":     {"statut": "OUI", "score": 0.50, "detail": "Recyclable, filière en développement"},
    "platre":     {"statut": "OUI", "score": 0.50, "detail": "Recyclable, filière en développement"},
    "gypsum":     {"statut": "OUI", "score": 0.50, "detail": "Recyclable, filière en développement"},
    "plaster":    {"statut": "OUI", "score": 0.50, "detail": "Recyclable, filière en développement"},
    "gyps":       {"statut": "OUI", "score": 0.50, "detail": "Recyclable, filière en développement"},

    # --- Isolants : recyclabilité très variable ---
    "laine":      {"statut": "OUI", "score": 0.40, "detail": "Partiellement recyclable selon composition"},
    "wool":       {"statut": "OUI", "score": 0.40, "detail": "Partiellement recyclable selon composition"},
    "rockwool":   {"statut": "OUI", "score": 0.35, "detail": "Recyclable en filière spécialisée"},
    "glasswool":  {"statut": "OUI", "score": 0.35, "detail": "Recyclable en filière spécialisée"},

    # --- Plastiques / composites : difficilement recyclables ---
    "plastique":  {"statut": "NON", "score": 0.15, "detail": "Peu recyclable en BTP, valorisation énergétique"},
    "plastic":    {"statut": "NON", "score": 0.15, "detail": "Peu recyclable en BTP, valorisation énergétique"},
    "pvc":        {"statut": "NON", "score": 0.20, "detail": "Recyclable en filière dédiée, limité"},
    "polystyrene":{"statut": "NON", "score": 0.10, "detail": "Très peu recyclable, valorisation énergétique"},
    "polystyrène":{"statut": "NON", "score": 0.10, "detail": "Très peu recyclable, valorisation énergétique"},
    "polyuréthane":{"statut": "NON", "score": 0.10, "detail": "Non recyclable, valorisation énergétique"},
    "polyurethane":{"statut": "NON", "score": 0.10, "detail": "Non recyclable, valorisation énergétique"},
    "composite":  {"statut": "NON", "score": 0.10, "detail": "Matériau composite, très difficile à recycler"},
    "résine":     {"statut": "NON", "score": 0.10, "detail": "Non recyclable en l'état"},
    "resin":      {"statut": "NON", "score": 0.10, "detail": "Non recyclable en l'état"},

    # --- Matériaux spéciaux ---
    "bitume":     {"statut": "OUI", "score": 0.55, "detail": "Recyclable en enrobé, filière routière"},
    "bitumen":    {"statut": "OUI", "score": 0.55, "detail": "Recyclable en enrobé, filière routière"},
    "asphalte":   {"statut": "OUI", "score": 0.55, "detail": "Recyclable, filière routière"},
    "asphalt":    {"statut": "OUI", "score": 0.55, "detail": "Recyclable, filière routière"},
    "terre":      {"statut": "OUI", "score": 0.70, "detail": "Réutilisable en remblai ou construction"},
    "earth":      {"statut": "OUI", "score": 0.70, "detail": "Réutilisable en remblai ou construction"},
}


# ============================================================
# RÉUTILISABILITÉ — Règles métier basées sur la démontabilité
# ============================================================
# Score 0.0 à 1.0 basé sur :
#   - Facilité de démontage sans dommage
#   - Existence d'un marché de réemploi
#   - Durabilité du composant après démontage
#   - Standardisation (dimensions courantes)
# ============================================================
TYPES_REUTILISABILITE = {
    "Fenêtre": {
        "statut": "OUI",
        "score": 0.75,
        "detail": "Démontable, marché de réemploi actif, vérifier état des joints",
    },
    "Porte": {
        "statut": "OUI",
        "score": 0.80,
        "detail": "Facilement démontable, forte demande en réemploi",
    },
    "Escalier": {
        "statut": "OUI",
        "score": 0.60,
        "detail": "Réutilisable si préfabriqué, démontage complexe si coulé en place",
    },
    "Mur rideau": {
        "statut": "OUI",
        "score": 0.70,
        "detail": "Réutilisable, système modulaire, nécessite expertise au démontage",
    },
    "Mur": {
        "statut": "NON",
        "score": 0.15,
        "detail": "Généralement non réutilisable, coulé en place ou maçonné",
    },
    "Dalle": {
        "statut": "NON",
        "score": 0.10,
        "detail": "Non réutilisable, élément structurel coulé en place",
    },
}

# Bonus de score réutilisation si matériau facilite le démontage
BONUS_REUTILISATION_MATERIAU = {
    "acier": 0.15,     # Assemblages boulonnés = démontables
    "steel": 0.15,
    "bois": 0.10,      # Assemblages vissés/cloués = démontables
    "wood": 0.10,
    "timber": 0.10,
    "aluminium": 0.10, # Profilés démontables
    "aluminum": 0.10,
}


def calculer_volume(hauteur: Optional[float], longueur: Optional[float],
                    epaisseur: Optional[float]) -> Optional[float]:
    """
    Calcule le volume d'un élément à partir de ses dimensions.
    volume = hauteur × longueur × épaisseur
    
    Returns:
        Volume en m³ ou None si dimensions insuffisantes
    """
    if hauteur and longueur and epaisseur:
        return round(hauteur * longueur * epaisseur, 4)
    return None


def determiner_recyclabilite(materiau: str) -> Dict[str, Any]:
    """
    Détermine la recyclabilité d'un matériau selon les règles métier BTP.
    Cherche par correspondance partielle dans le nom du matériau.
    
    Returns:
        Dict avec "statut" (OUI/NON/INCONNU), "score" (0-1), "detail"
    """
    if not materiau or materiau == "Inconnu":
        return {
            "statut": "INCONNU",
            "score": 0.0,
            "detail": "Matériau non identifié, recyclabilité inconnue",
        }

    materiau_lower = materiau.lower()

    # Chercher le meilleur match (le plus long mot-clé trouvé)
    best_match = None
    best_len = 0
    for mot_cle, info in MATERIAUX_RECYCLABILITE.items():
        if mot_cle in materiau_lower and len(mot_cle) > best_len:
            best_match = info
            best_len = len(mot_cle)

    if best_match:
        return best_match

    return {
        "statut": "INCONNU",
        "score": 0.0,
        "detail": f"Matériau « {materiau} » non référencé, recyclabilité inconnue",
    }


def determiner_reutilisabilite(type_element: str, materiau: str = "") -> Dict[str, Any]:
    """
    Détermine la réutilisabilité d'un élément selon son type et son matériau.
    Le matériau peut ajouter un bonus (ex: acier = assemblages boulonnés).
    
    Returns:
        Dict avec "statut" (OUI/NON), "score" (0-1), "detail"
    """
    base = TYPES_REUTILISABILITE.get(type_element, {
        "statut": "NON",
        "score": 0.10,
        "detail": "Type non référencé, réutilisation peu probable",
    })

    # Copier pour ne pas modifier le dictionnaire de référence
    result = {**base}

    # Appliquer le bonus matériau si applicable
    if materiau:
        materiau_lower = materiau.lower()
        for mot_cle, bonus in BONUS_REUTILISATION_MATERIAU.items():
            if mot_cle in materiau_lower:
                result["score"] = min(1.0, result["score"] + bonus)
                result["detail"] += f" (+bonus {mot_cle}: assemblage démontable)"
                break

    # Plafonner le score à 1.0
    result["score"] = round(min(1.0, result["score"]), 2)

    return result


def enrichir_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrichit la liste d'éléments avec volume, recyclabilité et réutilisabilité.
    Chaque élément reçoit un statut + score pour recyclage et réemploi.
    """
    enriched = []
    for elem in elements:
        # Calculer le volume
        volume = calculer_volume(
            elem.get("hauteur"),
            elem.get("longueur"),
            elem.get("epaisseur")
        )

        materiau = elem.get("materiau", "")
        type_element = elem.get("type", "")

        # Déterminer recyclabilité (statut + score + détail)
        recycl = determiner_recyclabilite(materiau)

        # Déterminer réutilisabilité (statut + score + détail, avec bonus matériau)
        reutil = determiner_reutilisabilite(type_element, materiau)

        # Construire l'élément enrichi
        enriched_elem = {
            **elem,
            "volume": volume,
            "recyclable": recycl["statut"],
            "score_recyclabilite": recycl["score"],
            "detail_recyclabilite": recycl["detail"],
            "reutilisable": reutil["statut"],
            "score_reutilisabilite": reutil["score"],
            "detail_reutilisabilite": reutil["detail"],
        }
        enriched.append(enriched_elem)

    return enriched


def calculer_resume(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcule le résumé global des éléments analysés.
    Inclut les scores moyens de recyclabilité et réutilisabilité.
    """
    total = len(elements)

    if total == 0:
        return {
            "total": 0,
            "par_type": {},
            "pourcentage_recyclable": 0,
            "pourcentage_reutilisable": 0,
            "score_moyen_recyclabilite": 0,
            "score_moyen_reutilisabilite": 0,
        }

    # Comptage par type
    par_type = {}
    for elem in elements:
        type_name = elem.get("type", "Inconnu")
        par_type[type_name] = par_type.get(type_name, 0) + 1

    # Pourcentage recyclable (OUI)
    nb_recyclable = sum(1 for e in elements if e.get("recyclable") == "OUI")
    pourcentage_recyclable = round((nb_recyclable / total) * 100, 1)

    # Pourcentage réutilisable (OUI)
    nb_reutilisable = sum(1 for e in elements if e.get("reutilisable") == "OUI")
    pourcentage_reutilisable = round((nb_reutilisable / total) * 100, 1)

    # Score moyen de recyclabilité (0 à 1)
    scores_recycl = [e.get("score_recyclabilite", 0) for e in elements]
    score_moyen_recyclabilite = round(sum(scores_recycl) / total, 2)

    # Score moyen de réutilisabilité (0 à 1)
    scores_reutil = [e.get("score_reutilisabilite", 0) for e in elements]
    score_moyen_reutilisabilite = round(sum(scores_reutil) / total, 2)

    return {
        "total": total,
        "par_type": par_type,
        "pourcentage_recyclable": pourcentage_recyclable,
        "pourcentage_reutilisable": pourcentage_reutilisable,
        "score_moyen_recyclabilite": score_moyen_recyclabilite,
        "score_moyen_reutilisabilite": score_moyen_reutilisabilite,
    }
