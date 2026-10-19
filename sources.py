"""Accès aux API publiques de l'État (BAN, API Carto IGN, GPU, Géorisques, geo.api, DVF)."""
import csv, io, json, math, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import requests

UA = {"User-Agent": "dossier-parcellaire/1.0 (outil interne d'etude)"}
TIMEOUT = 30
BAN = "https://api-adresse.data.gouv.fr/search/"
GEO = "https://geo.api.gouv.fr/communes/"
CARTO = "https://apicarto.ign.fr/api/"
GEORISQUES = "https://georisques.gouv.fr/api/v1/"
DVF = "https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/communes/{dep}/{insee}.csv"
NATURE = ["natura-habitat", "natura-oiseaux", "znieff1", "znieff2", "pnr", "pn", "rnn", "rnr"]


def _get(url, **params):
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def suggest(q, limit=6):
    """Recherche / normalisation d'adresse via la Base Adresse Nationale."""
    feats = _get(BAN, q=q, limit=limit).json().get("features", [])
    out = []
    for f in feats:
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
        out.append(dict(label=p.get("label"), lon=lon, lat=lat, citycode=p.get("citycode"),
                        postcode=p.get("postcode"), city=p.get("city"), context=p.get("context"),
                        type=p.get("type")))
    return out


def point(lon, lat):
    return {"type": "Point", "coordinates": [lon, lat]}


def square(lon, lat, half_m):
    dy = half_m / 111320
    dx = half_m / (111320 * math.cos(math.radians(lat)))
    return {"type": "Polygon", "coordinates": [[[lon-dx, lat-dy], [lon+dx, lat-dy], [lon+dx, lat+dy],
                                                [lon-dx, lat+dy], [lon-dx, lat-dy]]]}


def carto(path, geom):
    r = _get(CARTO + path, geom=json.dumps(geom), _limit=200)
    return r.json().get("features", [])


def gr(path, **params):
    j = _get(GEORISQUES + path, **params).json()
    return j.get("data", j) if isinstance(j, dict) else j


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(a))


def dvf(insee, idu, lon, lat, radius=300):
    """Mutations DVF (open data DGFiP via Etalab) : sur la parcelle et dans un rayon."""
    dep = insee[:3] if insee.startswith("97") else insee[:2]
    year, muts = dt.date.today().year, {}
    for y in range(year - 5, year + 1):
        try:
            txt = _get(DVF.format(year=y, dep=dep, insee=insee)).content.decode("utf-8")
        except requests.RequestException:
            continue
        for row in csv.DictReader(io.StringIO(txt)):
            same = bool(idu) and row.get("id_parcelle") == idu
            near = False
            if not same and row.get("latitude") and row.get("longitude"):
                near = haversine(lat, lon, float(row["latitude"]), float(row["longitude"])) <= radius
            if not (same or near):
                continue
            m = muts.setdefault(row["id_mutation"], dict(
                date=row["date_mutation"], nature=row["nature_mutation"],
                valeur=float(row["valeur_fonciere"] or 0),
                adresse=" ".join(x for x in [row["adresse_numero"], row["adresse_nom_voie"]] if x),
                types=set(), bati=0.0, terrain=0.0, same=False))
            m["same"] |= same
            if row["type_local"]:
                m["types"].add(row["type_local"])
            m["bati"] += float(row["surface_reelle_bati"] or 0)
            m["terrain"] += float(row["surface_terrain"] or 0)
    allm = sorted(muts.values(), key=lambda m: m["date"], reverse=True)
    for m in allm:
        m["types"] = ", ".join(sorted(m["types"]))
    return {"parcelle": [m for m in allm if m["same"]],
            "proches": [m for m in allm if not m["same"]][:15]}


def _safe(fn):
    try:
        return {"data": fn(), "error": None}
    except Exception as ex:  # une source en panne ne doit pas bloquer le dossier
        return {"data": None, "error": f"{type(ex).__name__}: {ex}"}


def collect(place):
    lon, lat, insee = place["lon"], place["lat"], place["citycode"]
    ll, pt, box = f"{lon},{lat}", point(lon, lat), square(lon, lat, 25)
    T = {
        "commune": lambda: _get(GEO + insee, fields="nom,code,codesPostaux,population,surface,departement,region,epci").json(),
        "parcelle": lambda: carto("cadastre/parcelle", pt),
        "voisines": lambda: carto("cadastre/parcelle", square(lon, lat, 70)),
        "zone_urba": lambda: carto("gpu/zone-urba", pt),
        "document": lambda: carto("gpu/document", pt),
    }
    for k in ("prescription-surf", "prescription-lin", "prescription-pct", "info-surf", "info-lin", "info-pct"):
        T["gpu:" + k] = lambda k=k: carto("gpu/" + k, pt if k.endswith("surf") else box)
    for k in ("assiette-sup-s", "assiette-sup-l", "assiette-sup-p"):
        T["sup:" + k] = lambda k=k: carto("gpu/" + k, pt if k.endswith("-s") else box)
    for k in NATURE:
        T["nat:" + k] = lambda k=k: carto("nature/" + k, pt)
    GR = {
        "rga": ("rga", {"latlon": ll}),
        "radon": ("radon", {"code_insee": insee}),
        "sismique": ("zonage_sismique", {"code_insee": insee}),
        "risques": ("gaspar/risques", {"code_insee": insee}),
        "azi": ("gaspar/azi", {"code_insee": insee}),
        "pprn": ("gaspar/pprn", {"code_insee": insee}),
        "catnat": ("gaspar/catnat", {"code_insee": insee, "page_size": 100}),
        "mvt": ("mvt", {"latlon": ll, "rayon": 500}),
        "cavites": ("cavites", {"latlon": ll, "rayon": 500}),
        "casias": ("ssp/casias", {"latlon": ll, "rayon": 500}),
        "sis": ("ssp/sis", {"latlon": ll, "rayon": 500}),
        "icpe": ("installations_classees", {"latlon": ll, "rayon": 1000}),
    }
    for k, (path, prm) in GR.items():
        T["gr:" + k] = lambda path=path, prm=prm: gr(path, **prm)
    with ThreadPoolExecutor(8) as ex:
        futs = {k: ex.submit(_safe, fn) for k, fn in T.items()}
        D = {k: f.result() for k, f in futs.items()}
    parc = D["parcelle"]["data"] or []
    idu = parc[0]["properties"].get("idu") if parc else None
    D["dvf"] = _safe(lambda: dvf(insee, idu, lon, lat))
    D["_date"] = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    return D
