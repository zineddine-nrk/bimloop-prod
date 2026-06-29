"""
Package d'extracteurs IFC — un module par type de composant.
"""

from extractors.walls import extract_wall_data
from extractors.windows import extract_window_data
from extractors.doors import extract_door_data
from extractors.slabs import extract_slab_data
from extractors.stairs import extract_stair_data
from extractors.curtain_walls import extract_curtain_wall_data

# Correspondance type IFC → (nom français, fonction d'extraction)
EXTRACTOR_MAP = {
    "IfcWall": ("Mur", extract_wall_data),
    "IfcWindow": ("Fenêtre", extract_window_data),
    "IfcDoor": ("Porte", extract_door_data),
    "IfcSlab": ("Dalle", extract_slab_data),
    "IfcStair": ("Escalier", extract_stair_data),
    "IfcCurtainWall": ("Mur rideau", extract_curtain_wall_data),
}

__all__ = [
    "EXTRACTOR_MAP",
    "extract_wall_data",
    "extract_window_data",
    "extract_door_data",
    "extract_slab_data",
    "extract_stair_data",
    "extract_curtain_wall_data",
]
