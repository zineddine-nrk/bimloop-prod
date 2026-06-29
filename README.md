# IFC Analyzer — Extraction & Tracking (Production)

Application web pour analyser des fichiers IFC et suivre le cycle de vie des composants de construction.

## Fonctionnalites

- **Upload** de fichiers `.ifc`
- **Extraction** automatique : Murs, Fenetres, Portes, Dalles, Escaliers, Murs rideaux
- **Dimensions** : hauteur, longueur, epaisseur, volume
- **Materiaux** : extraction automatique depuis le fichier IFC
- **Durabilite** : recyclabilite et reutilisabilite de chaque element
- **Tracking** : suivi du cycle de vie des composants (en place, demonte, transporte, stocke, reutilise/recycle)
- **QR codes** : generation de QR codes par composant
- **Exports reglementaires** : CERFA PEMD, dechets inertes (DI), BTP Match
- **Authentification JWT** avec roles `user`/`admin`
- **Filtres** dynamiques par type d'element
- **Resume** global avec statistiques et pourcentages

## Structure du projet

```
├── backend/
│   ├── main.py              # Serveur FastAPI
│   ├── ifc_parser.py        # Extraction des donnees IFC
│   ├── tracker.py           # Tracking du cycle de vie
│   ├── ifc_exporter.py      # Export IFC enrichi
│   ├── utils.py             # Calculs et regles de durabilite
│   ├── auth_*.py            # Authentification JWT
│   ├── pemd_pdf.py          # CERFA PEMD PDF
│   ├── di_csv.py/di_pdf.py  # Dechets inertes
│   ├── reuse_csv.py         # CSV reemploi
│   ├── btp_match_pdf.py     # BTP Match PDF
│   ├── table_pdf.py         # Table PDF generique
│   ├── extraction_pemd_pdf.py
│   └── extractors/          # Extracteurs specialises (murs, fenetres, etc.)
├── frontend/
│   ├── index.html           # Page extraction
│   ├── tracker.html         # Dashboard tracking
│   ├── tracker_detail.html  # Detail composant
│   ├── login.html           # Connexion
│   ├── settings.html        # Parametres
│   ├── script.js            # Logique extraction
│   ├── auth.js              # Gestion tokens JWT
│   └── assets/              # CSS, JS partages
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Lancement avec Docker

```bash
docker compose up -d
```

L'application sera accessible sur **http://localhost:8000**

## Lancement local

### Prerequis
- Python 3.9+
- PostgreSQL

### Installation

```bash
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt

set DATABASE_URL=postgresql+psycopg://bimloop:bimloop@localhost:5432/bimloop
set JWT_SECRET_KEY=change-me

cd backend
python main.py
```

## Stack technique

- **Backend** : Python, FastAPI, ifcopenshell
- **Auth** : JWT, PostgreSQL / SQLite
- **Frontend** : HTML, CSS, JavaScript (vanilla)
- **PDF** : ReportLab
- **QR codes** : qrcode[pil]
