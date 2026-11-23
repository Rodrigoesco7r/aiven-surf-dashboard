"""
Dashboard de Surf — App Flask
Exibe condições de ondas e marés nos principais spots de surf do Brasil.
Dados buscados da Open-Meteo Marine API e persistidos no PostgreSQL da Aiven.

Variáveis de ambiente:
  AIVEN_DB_URL  -> string de conexão da Aiven
  PORT          -> porta HTTP (default 8080)
  CACHE_HOURS   -> horas antes de buscar dados novos (default 3)
"""

import os
import time
import datetime
from flask import Flask, render_template, jsonify, request
import surf_client as surf

app = Flask(__name__)
START_TIME = time.time()

# Inicializa tabelas e faz o primeiro carregamento de dados
surf.init_db()


@app.route("/")
def dashboard():
    surf.log_visit("/")
    surf.refresh_all_spots()
    spots = surf.get_all_spots()

    # Converte RealDictRow para dict serializável
    spots_list = []
    for s in spots:
        d = dict(s)
        if d.get("fetched_at"):
            d["fetched_at"] = d["fetched_at"].strftime("%d/%m/%Y %H:%M")
        spots_list.append(d)

    total_visits = surf.get_total_visits()
    uptime = int(time.time() - START_TIME)

    return render_template(
        "dashboard.html",
        spots=spots_list,
        total_visits=total_visits,
        uptime=uptime,
        server_time=datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC"),
    )


@app.route("/api/surf")
def api_surf():
    surf.log_visit("/api/surf")
    surf.refresh_all_spots()
    spots = surf.get_all_spots()
    spots_list = []
    for s in spots:
        d = dict(s)
        if d.get("fetched_at"):
            d["fetched_at"] = d["fetched_at"].isoformat()
        spots_list.append(d)
    return jsonify({"spots": spots_list, "total": len(spots_list)})


@app.route("/api/tides/<spot_id>")
def api_tides(spot_id):
    rows = surf.get_tide_data(spot_id)
    data = [{"ts": str(r["ts"]), "height": r["tide_height"]} for r in rows]
    return jsonify({"spot_id": spot_id, "tides": data})


@app.route("/healthz")
def healthz():
    try:
        with surf.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        return jsonify({"status": "error", "detail": str(exc)}), 503


if __name__ == "__main__":
    surf.refresh_all_spots()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
