import hmac, io, os, re
from flask import Flask, Response, jsonify, render_template, request, send_file
import maps, report, sources

app = Flask(__name__)


@app.before_request
def protect():
    """Si la variable APP_PASSWORD est définie (hébergement), demande un mot de passe (identifiant libre)."""
    pw = os.environ.get("APP_PASSWORD")
    if not pw:
        return None
    a = request.authorization
    if not a or not hmac.compare_digest(a.password or "", pw):
        return Response("Authentification requise", 401, {"WWW-Authenticate": 'Basic realm="Dossier parcellaire"'})


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/suggest")
def api_suggest():
    q = request.args.get("q", "").strip()
    if len(q) < 3:
        return jsonify([])
    try:
        return jsonify(sources.suggest(q))
    except Exception as ex:
        return jsonify(error=str(ex)), 502


@app.post("/api/dossier")
def api_dossier():
    body = request.get_json(force=True)
    place = body if body.get("lon") else None
    if not place:
        found = sources.suggest(body.get("q", ""), 1)
        if not found:
            return jsonify(error="Adresse introuvable"), 404
        place = found[0]
    D = sources.collect(place)
    pdf = report.build(place, D, maps.make_all(place, D))
    name = re.sub(r"[^A-Za-z0-9]+", "_", place["label"]).strip("_")
    return send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=f"dossier_{name}.pdf")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
