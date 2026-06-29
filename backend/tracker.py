"""
Module de tracking des composants IFC.
Base de données SQLite avec historique des changements de statut.
"""

import sqlite3
import io
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

import qrcode
from qrcode.image.pure import PyPNGImage

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "tracker.db")

# Statuts valides et leur ordre logique
STATUTS_VALIDES = ["in_building", "démonté", "transporté", "stocké", "réutilisé", "à réutiliser", "à recycler"]


# ============================================================
# INITIALISATION DB
# ============================================================

def init_db():
    """Crée les tables et migre les anciennes données si nécessaire."""
    with sqlite3.connect(DB_PATH) as conn:
        # Table projects
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id          TEXT PRIMARY KEY,
                type        TEXT,
                material    TEXT,
                ifc_location TEXT,
                status      TEXT DEFAULT 'in_building',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id TEXT NOT NULL,
                old_status  TEXT,
                new_status  TEXT NOT NULL,
                note        TEXT,
                changed_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (component_id) REFERENCES components(id)
            )
        """)

        # Migration : colonnes pour stocker l'IFC source du projet
        proj_cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "ifc_filename" not in proj_cols:
            conn.execute("ALTER TABLE projects ADD COLUMN ifc_filename TEXT")
        if "ifc_path" not in proj_cols:
            conn.execute("ALTER TABLE projects ADD COLUMN ifc_path TEXT")

        # Migration : nouvelles colonnes metadata (condition, comment, lifespan)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(components)").fetchall()]
        if "condition" not in cols:
            conn.execute("ALTER TABLE components ADD COLUMN condition TEXT")
        if "comment" not in cols:
            conn.execute("ALTER TABLE components ADD COLUMN comment TEXT")
        if "lifespan_months" not in cols:
            conn.execute("ALTER TABLE components ADD COLUMN lifespan_months INTEGER DEFAULT 0")
        if "age_estimated" not in cols:
            conn.execute("ALTER TABLE components ADD COLUMN age_estimated TEXT")
        # Migration : dimensions stockées au moment de l'import (utile pour DI CSV
        # quand l'IFC source n'est pas uploadé après coup).
        for dim_col in ("hauteur", "longueur", "epaisseur", "net_area", "net_volume"):
            if dim_col not in cols:
                conn.execute(f"ALTER TABLE components ADD COLUMN {dim_col} REAL")

        # Migration : ajouter project_id si absent + rattacher les anciennes données
        if "project_id" not in cols:
            conn.execute("ALTER TABLE components ADD COLUMN project_id INTEGER")
            # S'il existe des composants orphelins → créer un projet legacy
            orphan_count = conn.execute(
                "SELECT COUNT(*) FROM components WHERE project_id IS NULL"
            ).fetchone()[0]
            if orphan_count > 0:
                cur = conn.execute(
                    "INSERT INTO projects (name) VALUES (?)",
                    ("Projet legacy (avant multi-projets)",),
                )
                legacy_id = cur.lastrowid
                conn.execute(
                    "UPDATE components SET project_id = ? WHERE project_id IS NULL",
                    (legacy_id,),
                )

        # Index pour les requêtes par projet
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_components_project ON components(project_id)"
        )

        # Migration user_id (après l'éventuelle création du projet legacy)
        proj_cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "user_id" not in proj_cols:
            conn.execute("ALTER TABLE projects ADD COLUMN user_id INTEGER")
        conn.execute("UPDATE projects SET user_id = 1 WHERE user_id IS NULL")

        # Migration : colonnes PEMD (CERFA) pour l'éditeur PEMD
        cols = [r[1] for r in conn.execute("PRAGMA table_info(components)").fetchall()]
        pem_cols = [
            "pem_category", "pem_description", "pem_quantity", "pem_dimensions",
            "pem_assembly_type", "pem_age", "pem_condition", "pem_hazardous",
            "pem_materials", "pem_location", "pem_reuse_conditions",
            "pem_tech_info", "pem_transport_precautions"
        ]
        for pem_col in pem_cols:
            if pem_col not in cols:
                if pem_col.startswith("pem_hazardous") or pem_col.startswith("pem_location") or pem_col.startswith("pem_reuse") or pem_col.startswith("pem_tech") or pem_col.startswith("pem_transport"):
                    conn.execute(f"ALTER TABLE components ADD COLUMN {pem_col} INTEGER DEFAULT 0")
                else:
                    conn.execute(f"ALTER TABLE components ADD COLUMN {pem_col} TEXT")
        conn.commit()


# ============================================================
# PROJETS
# ============================================================

def create_project(name: str, user_id: int) -> int:
    """Crée un nouveau projet et retourne son id."""
    init_db()
    name = (name or "").strip() or f"Projet du {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, user_id) VALUES (?, ?)", (name, user_id)
        )
        conn.commit()
        return cur.lastrowid


def list_projects(user_id: Optional[int] = None) -> List[Dict]:
    """Liste les projets avec le nombre de composants de chacun.
    Si user_id est fourni, filtre sur cet utilisateur."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        query = """
            SELECT p.id, p.name, p.created_at, p.user_id,
                   COUNT(c.id) AS component_count
            FROM projects p
            LEFT JOIN components c ON c.project_id = p.id
        """
        params = []
        if user_id is not None:
            query += " WHERE p.user_id = ?"
            params.append(user_id)
        query += " GROUP BY p.id ORDER BY p.created_at DESC"
        cur = conn.execute(query, params)
        return [_row_to_dict(r, cur) for r in cur.fetchall()]


def get_project(project_id: int) -> Optional[Dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cur.fetchone()
        return _row_to_dict(row, cur) if row else None



def delete_project(project_id: int) -> Dict[str, int]:
    """Supprime un projet, ses composants et son historique."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        # Récupérer les ids des composants du projet
        comp_ids = [r[0] for r in conn.execute(
            "SELECT id FROM components WHERE project_id = ?", (project_id,)
        ).fetchall()]
        # Supprimer l'historique
        history_deleted = 0
        if comp_ids:
            placeholders = ",".join("?" * len(comp_ids))
            cur = conn.execute(
                f"DELETE FROM status_history WHERE component_id IN ({placeholders})",
                comp_ids,
            )
            history_deleted = cur.rowcount
        # Supprimer les composants
        cur = conn.execute(
            "DELETE FROM components WHERE project_id = ?", (project_id,)
        )
        components_deleted = cur.rowcount
        # Supprimer le projet
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        project_deleted = cur.rowcount
        conn.commit()
    return {
        "project_deleted": project_deleted,
        "components_deleted": components_deleted,
        "history_deleted": history_deleted,
    }


# ============================================================
# IMPORT DEPUIS JSON IFC
# ============================================================

def import_components(components: List[Dict],
                     project_name: Optional[str] = None,
                     user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Crée un NOUVEAU projet et y importe les composants.
    Si un composant avec le même IFC id existe déjà dans la base (autre projet),
    on duplique l'enregistrement en le rattachant au nouveau projet (PK composite
    simulée via suffixe). Pour rester simple : on garde id TEXT PK unique en réutilisant
    l'id IFC tel quel — si conflit, on suffixe avec _p{project_id}.
    Retourne {project_id, project_name, created, updated}.
    """
    init_db()
    if user_id is None:
        raise ValueError("user_id est requis pour la création d'un projet.")
    project_id = create_project(project_name, user_id)
    created = 0
    skipped = 0
    with sqlite3.connect(DB_PATH) as conn:
        # Récupérer le nom enregistré (utile si auto-généré)
        proj_name = conn.execute(
            "SELECT name FROM projects WHERE id = ?", (project_id,)
        ).fetchone()[0]

        for c in components:
            ifc_id = c.get("id")
            if not ifc_id:
                continue

            # Si l'IFC id existe déjà dans la base, on le suffixe pour ce projet
            existing = conn.execute(
                "SELECT id FROM components WHERE id = ?", (ifc_id,)
            ).fetchone()
            stored_id = ifc_id if not existing else f"{ifc_id}__p{project_id}"

            def _f(v):
                try: return float(v) if v not in (None, "") else None
                except (TypeError, ValueError): return None

            try:
                conn.execute("""
                    INSERT INTO components
                        (id, type, material, ifc_location, status, project_id,
                         hauteur, longueur, epaisseur, net_area, net_volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stored_id, c.get("type"), c.get("material"),
                    c.get("ifc_location"), c.get("status", "in_building"),
                    project_id,
                    _f(c.get("hauteur")), _f(c.get("longueur")), _f(c.get("epaisseur")),
                    _f(c.get("net_area")), _f(c.get("net_volume")),
                ))
                conn.execute("""
                    INSERT INTO status_history
                        (component_id, old_status, new_status, note)
                    VALUES (?, NULL, ?, 'Import initial IFC')
                """, (stored_id, c.get("status", "in_building")))
                created += 1
            except sqlite3.IntegrityError:
                skipped += 1
        conn.commit()
    return {
        "project_id": project_id,
        "project_name": proj_name,
        "created": created,
        "skipped": skipped,
    }


# ============================================================
# LECTURE
# ============================================================

def _row_to_dict(row, cursor) -> Dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def get_all_components(project_id: Optional[int] = None,
                       status_filter: Optional[str] = None,
                       type_filter: Optional[str] = None) -> List[Dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT * FROM components WHERE 1=1"
        params: List[Any] = []
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)
        query += " ORDER BY updated_at DESC"
        cur = conn.execute(query, params)
        return [_row_to_dict(r, cur) for r in cur.fetchall()]


def get_component(component_id: str) -> Optional[Dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM components WHERE id = ?", (component_id,))
        row = cur.fetchone()
        if not row:
            return None
        comp = _row_to_dict(row, cur)
        # Charger l'historique
        cur2 = conn.execute("""
            SELECT * FROM status_history
            WHERE component_id = ?
            ORDER BY changed_at DESC
        """, (component_id,))
        comp["history"] = [_row_to_dict(r, cur2) for r in cur2.fetchall()]
        return comp


# ============================================================
# CHANGEMENT DE STATUT
# ============================================================

def update_status(component_id: str, new_status: str,
                  note: Optional[str] = None) -> Dict[str, Any]:
    """Met à jour le statut d'un composant et enregistre l'historique."""
    if new_status not in STATUTS_VALIDES:
        raise ValueError(f"Statut invalide : {new_status}. Valeurs : {STATUTS_VALIDES}")

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT status FROM components WHERE id = ?", (component_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Composant introuvable : {component_id}")

        old_status = row[0]
        conn.execute("""
            UPDATE components SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (new_status, component_id))
        conn.execute("""
            INSERT INTO status_history (component_id, old_status, new_status, note)
            VALUES (?, ?, ?, ?)
        """, (component_id, old_status, new_status, note))
        conn.commit()

    return {"id": component_id, "old_status": old_status, "new_status": new_status}


# ============================================================
# METADATA (condition, commentaire, durée de vie)
# ============================================================

CONDITIONS_VALIDES = ["Neuf", "Bon", "Moyen", "Mauvais"]
AGES_VALIDES = [
    "Inférieur à 2 ans",
    "Entre 2 et 10 ans",
    "Entre 10 et 50 ans",
    "Supérieur à 50 ans",
]

def update_component_meta(component_id: str,
                          condition: Optional[str] = None,
                          comment: Optional[str] = None,
                          lifespan_months: Optional[int] = None,
                          age_estimated: Optional[str] = None) -> Dict[str, Any]:
    """Met à jour les métadonnées d'un composant (condition / commentaire / durée / âge estimé)."""
    if condition is not None and condition != "" and condition not in CONDITIONS_VALIDES:
        raise ValueError(f"Condition invalide. Valeurs : {CONDITIONS_VALIDES}")
    if age_estimated is not None and age_estimated != "" and age_estimated not in AGES_VALIDES:
        raise ValueError(f"Âge estimé invalide. Valeurs : {AGES_VALIDES}")
    if lifespan_months is not None and lifespan_months < 0:
        raise ValueError("La durée de vie doit être >= 0.")

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM components WHERE id = ?", (component_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Composant introuvable : {component_id}")

        sets, params = [], []
        if condition is not None:
            sets.append("condition = ?"); params.append(condition)
        if comment is not None:
            sets.append("comment = ?"); params.append(comment)
        if lifespan_months is not None:
            sets.append("lifespan_months = ?"); params.append(int(lifespan_months))
        if age_estimated is not None:
            sets.append("age_estimated = ?"); params.append(age_estimated or None)
        if not sets:
            return {"id": component_id, "updated": 0}
        sets.append("updated_at = datetime('now')")
        params.append(component_id)
        conn.execute(
            f"UPDATE components SET {', '.join(sets)} WHERE id = ?", params
        )
        conn.commit()
    return {"id": component_id, "updated": 1}


# ============================================================
# STATUTS PAR IDS (pour affichage dans tableau principal)
# ============================================================

def get_statuses_by_ids(ids: List[str],
                        project_id: Optional[int] = None,
                        user_id: Optional[int] = None) -> Dict[str, str]:
    """Retourne {ifc_id: status} pour une liste d'IDs IFC.
    Si project_id est fourni, filtre sur ce projet.
    Si user_id est fourni, filtre sur les projets de cet utilisateur.
    Sinon : prend le statut du composant le plus récemment mis à jour.
    Note : on matche soit l'id exact, soit la forme suffixée 'id__pX'.
    """
    init_db()
    if not ids:
        return {}
    out: Dict[str, str] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for ifc_id in ids:
            if project_id is not None:
                # Cherche soit l'id direct, soit la forme suffixée pour ce projet
                row = conn.execute(
                    """SELECT status FROM components
                       WHERE project_id = ? AND (id = ? OR id = ?)
                       LIMIT 1""",
                    (project_id, ifc_id, f"{ifc_id}__p{project_id}"),
                ).fetchone()
            elif user_id is not None:
                # Filtre par les projets de l'utilisateur
                row = conn.execute(
                    """SELECT c.status FROM components c
                       JOIN projects p ON c.project_id = p.id
                       WHERE p.user_id = ? AND (c.id = ? OR c.id LIKE ?)
                       ORDER BY c.updated_at DESC LIMIT 1""",
                    (user_id, ifc_id, f"{ifc_id}__p%"),
                ).fetchone()
            else:
                # Statut le plus récent (toutes projets confondus)
                row = conn.execute(
                    """SELECT status FROM components
                       WHERE id = ? OR id LIKE ?
                       ORDER BY updated_at DESC LIMIT 1""",
                    (ifc_id, f"{ifc_id}__p%"),
                ).fetchone()
            if row:
                out[ifc_id] = row[0]
    return out


# ============================================================
# METADATA COMPLET PAR IDS (pour l'export IFC enrichi)
# ============================================================

def get_components_meta_by_ids(ids: List[str],
                               project_id: Optional[int] = None) -> Dict[str, Dict]:
    """Pour chaque IFC GlobalId, retourne le dict complet du composant
    (status, condition, comment, lifespan_months, updated_at) + last_note depuis history.

    Si project_id est fourni : filtre sur ce projet.
    Sinon : composant le plus récemment mis à jour (tous projets confondus).
    """
    init_db()
    if not ids:
        return {}
    out: Dict[str, Dict] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for ifc_id in ids:
            if project_id is not None:
                row_cur = conn.execute(
                    """SELECT * FROM components
                       WHERE project_id = ? AND (id = ? OR id = ?)
                       LIMIT 1""",
                    (project_id, ifc_id, f"{ifc_id}__p{project_id}"),
                )
            else:
                row_cur = conn.execute(
                    """SELECT * FROM components
                       WHERE id = ? OR id LIKE ?
                       ORDER BY updated_at DESC LIMIT 1""",
                    (ifc_id, f"{ifc_id}__p%"),
                )
            row = row_cur.fetchone()
            if not row:
                continue
            comp = _row_to_dict(row, row_cur)
            # Dernière note non-nulle de l'historique
            note_row = conn.execute(
                """SELECT note FROM status_history
                   WHERE component_id = ? AND note IS NOT NULL AND note != ''
                   ORDER BY changed_at DESC LIMIT 1""",
                (comp["id"],),
            ).fetchone()
            comp["last_note"] = note_row[0] if note_row else None
            out[ifc_id] = comp
    return out


# ============================================================
# QR CODE
# ============================================================

def generate_qr_png(component_id: str, base_url: str,
                    project_id: Optional[int] = None) -> bytes:
    """Génère un QR code PNG pointant vers la page détail du composant."""
    if project_id is not None:
        url = f"{base_url}/tracker/{project_id}/{component_id}"
    else:
        url = f"{base_url}/tracker/{component_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================
# VÉRIFICATION PROPRIÉTÉ UTILISATEUR
# ============================================================

def project_belongs_to_user(project_id: int, user_id: int) -> bool:
    """Vérifie qu'un projet appartient à l'utilisateur donné."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT user_id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return row is not None and row[0] == user_id


def component_belongs_to_user(component_id: str, user_id: int) -> bool:
    """Vérifie qu'un composant appartient (via son projet) à l'utilisateur donné."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT p.user_id FROM projects p
            JOIN components c ON c.project_id = p.id
            WHERE c.id = ?
        """, (component_id,)).fetchone()
        return row is not None and row[0] == user_id


def get_component_project_id(component_id: str) -> Optional[int]:
    """Retourne le project_id du composant, ou None."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT project_id FROM components WHERE id = ?", (component_id,)
        ).fetchone()
        return row[0] if row else None


# ============================================================
# STATS
# ============================================================

def get_stats(project_id: Optional[int] = None) -> Dict:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        where, params = ("", [])
        if project_id is not None:
            where = " WHERE project_id = ?"
            params = [project_id]
        total = conn.execute(
            f"SELECT COUNT(*) FROM components{where}", params
        ).fetchone()[0]
        by_status: Dict[str, int] = {}
        for row in conn.execute(
            f"SELECT status, COUNT(*) FROM components{where} GROUP BY status", params
        ).fetchall():
            by_status[row[0]] = row[1]
        by_type: Dict[str, int] = {}
        for row in conn.execute(
            f"SELECT type, COUNT(*) FROM components{where} GROUP BY type", params
        ).fetchall():
            by_type[row[0]] = row[1]
    return {"total": total, "by_status": by_status, "by_type": by_type}
