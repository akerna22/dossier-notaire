# Dossier parcellaire et urbanistique

Saisie d'une adresse en France -> PDF de ~10 pages (identification, cadastre, cartes, urbanisme/PLU, servitudes,
Géorisques, environnement, marché DVF, synthèse, sources).

## Installation (ordre à respecter)
1. Installer Python 3.10+ : https://www.python.org/downloads/ (Windows : cocher « Add python.exe to PATH »).
2. Dézipper le dossier, puis :
   - Windows : double-clic sur `lancer.bat`
   - Mac/Linux : `./lancer.sh`
   (ou à la main : `python -m venv .venv`, activer, `pip install -r requirements.txt`, `python app.py`)
3. Ouvrir http://127.0.0.1:5000, taper une adresse, choisir une suggestion, cliquer sur « Générer ».

## Fichiers
- `sources.py` : appels API (BAN, API Carto IGN cadastre/GPU/nature, Géorisques, geo.api.gouv.fr, DVF). Les chemins d'API sont regroupés ici.
- `maps.py` : fonds IGN (Géoplateforme WMS) + tracés des parcelles et du zonage.
- `report.py` : mise en page du PDF. `app.py` + `templates/index.html` : site local.

## Notes
- Aucune clé d'API n'est nécessaire. Une source en panne n'empêche pas le PDF : elle est signalée dans le document.
- Le PDF est une aide : il ne remplace ni le certificat d'urbanisme, ni l'ERP, ni l'extrait cadastral officiel.
- Si un chapitre sort vide alors que la source répond, l'API a peut-être changé : ajuster le chemin ou les clés dans `sources.py` / `report.py`.
