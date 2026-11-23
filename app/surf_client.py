"""
Cliente de dados de surf — Open-Meteo Marine API
Busca condições de ondas e marés para os principais spots de surf do Brasil.
Salva e atualiza os dados no PostgreSQL da Aiven.

Variáveis de ambiente esperadas:
  AIVEN_DB_URL  -> string de conexão fornecida pela Aiven
  CACHE_HOURS   -> horas antes de buscar dados novos (default 3)
"""

import os
import datetime
import requests
import psycopg2
import psycopg2.extras

AIVEN_DB_URL = os.environ.get("AIVEN_DB_URL")
CACHE_HOURS = int(os.environ.get("CACHE_HOURS", 3))

# Principais spots de surf do Brasil com coordenadas
SPOTS = [
    {"id": "fernando_noronha",    "name": "Fernando de Noronha", "state": "PE", "city": "Fernando de Noronha", "lat": -3.854,  "lon": -32.425},
    {"id": "itamambuca",          "name": "Itamambuca",           "state": "SP", "city": "Ubatuba",            "lat": -23.349, "lon": -44.897},
    {"id": "maresias",            "name": "Maresias",             "state": "SP", "city": "São Sebastião",      "lat": -23.797, "lon": -45.557},
    {"id": "saquarema",           "name": "Saquarema",            "state": "RJ", "city": "Saquarema",          "lat": -22.920, "lon": -42.510},
    {"id": "arpoador",            "name": "Arpoador",             "state": "RJ", "city": "Rio de Janeiro",     "lat": -22.987, "lon": -43.192},
    {"id": "floripa_joaquina",    "name": "Praia da Joaquina",    "state": "SC", "city": "Florianópolis",      "lat": -27.636, "lon": -48.445},
    {"id": "floripa_campeche",    "name": "Praia do Campeche",    "state": "SC", "city": "Florianópolis",      "lat": -27.697, "lon": -48.491},
    {"id": "torres",              "name": "Torres",               "state": "RS", "city": "Torres",             "lat": -29.336, "lon": -49.727},
    {"id": "porto_de_galinhas",   "name": "Porto de Galinhas",    "state": "PE", "city": "Ipojuca",            "lat": -8.706,  "lon": -35.022},
    {"id": "jericoacoara",        "name": "Jericoacoara",         "state": "CE", "city": "Jijoca de Jericoacoara", "lat": -2.796, "lon": -40.512},
    {"id": "canoa_quebrada",      "name": "Canoa Quebrada",       "state": "CE", "city": "Aracati",            "lat": -4.524,  "lon": -37.658},
    {"id": "itacare",             "name": "Itacaré",              "state": "BA", "city": "Itacaré",            "lat": -14.278, "lon": -38.998},
    {"id": "praia_do_forte",      "name": "Praia do Forte",       "state": "BA", "city": "Mata de São João",   "lat": -12.578, "lon": -38.002},
    {"id": "barra_da_tijuca",     "name": "Barra da Tijuca",      "state": "RJ", "city": "Rio de Janeiro",     "lat": -23.004, "lon": -43.365},
    {"id": "buzios",              "name": "Geribá",               "state": "RJ", "city": "Búzios",             "lat": -22.781, "lon": -41.884},
]


def get_connection():
    conn = psycopg2.connect(AIVEN_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS surf_spots (
                    spot_id       TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    state         TEXT NOT NULL,
                    city          TEXT NOT NULL,
                    lat           DOUBLE PRECISION,
                    lon           DOUBLE PRECISION,
                    wave_height   DOUBLE PRECISION,
                    wave_period   DOUBLE PRECISION,
                    wave_direction DOUBLE PRECISION,
                    wind_speed    DOUBLE PRECISION,
                    wind_direction DOUBLE PRECISION,
                    water_temp    DOUBLE PRECISION,
                    score         DOUBLE PRECISION,
                    fetched_at    TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tide_data (
                    id         SERIAL PRIMARY KEY,
                    spot_id    TEXT NOT NULL,
                    ts         TIMESTAMPTZ NOT NULL,
                    tide_height DOUBLE PRECISION,
                    UNIQUE(spot_id, ts)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS visits (
                    id      SERIAL PRIMARY KEY,
                    path    TEXT,
                    visited_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        conn.commit()


def is_cache_stale(spot_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fetched_at FROM surf_spots WHERE spot_id = %s;",
                (spot_id,)
            )
            row = cur.fetchone()
    if not row or not row["fetched_at"]:
        return True
    age = datetime.datetime.now(datetime.timezone.utc) - row["fetched_at"]
    return age > datetime.timedelta(hours=CACHE_HOURS)


def fetch_spot_data(spot: dict) -> dict:
    """Busca ondas, vento e temperatura da Open-Meteo Marine API."""
    url = "https://marine-api.open-meteo.com/v1/marine"
    params = {
        "latitude":  spot["lat"],
        "longitude": spot["lon"],
        "current": [
            "wave_height",
            "wave_period",
            "wave_direction",
            "wind_wave_height",
            "wind_wave_period",
        ],
        "hourly": ["wave_height", "wave_period", "sea_level_pressure"],
        "daily":  ["wave_height_max", "wave_period_max"],
        "timezone": "America/Sao_Paulo",
        "forecast_days": 1,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_wind_data(spot: dict) -> dict:
    """Busca vento e temperatura da água (Open-Meteo Forecast API)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  spot["lat"],
        "longitude": spot["lon"],
        "current": ["wind_speed_10m", "wind_direction_10m", "surface_temperature"],
        "timezone": "America/Sao_Paulo",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def calc_score(wave_height: float, wave_period: float) -> float:
    """
    Score simples de 0 a 10:
    - Ondas entre 1.0m e 2.5m são ideais
    - Período entre 10s e 16s é ideal
    """
    if not wave_height or not wave_period:
        return 0.0
    h_score = max(0, min(10, (wave_height - 0.3) * 4))
    if wave_height > 2.5:
        h_score = max(0, h_score - (wave_height - 2.5) * 3)
    p_score = max(0, min(10, (wave_period - 6) * 1.2))
    return round((h_score * 0.6 + p_score * 0.4), 2)


def upsert_spot(spot: dict, marine: dict, wind: dict):
    cur_marine = marine.get("current", {})
    cur_wind   = wind.get("current", {})

    wave_height   = cur_marine.get("wave_height")
    wave_period   = cur_marine.get("wave_period")
    wave_dir      = cur_marine.get("wave_direction")
    wind_speed    = cur_wind.get("wind_speed_10m")
    wind_dir      = cur_wind.get("wind_direction_10m")
    water_temp    = cur_wind.get("surface_temperature")
    score         = calc_score(wave_height or 0, wave_period or 0)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO surf_spots
                    (spot_id, name, state, city, lat, lon,
                     wave_height, wave_period, wave_direction,
                     wind_speed, wind_direction, water_temp, score, fetched_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                ON CONFLICT (spot_id) DO UPDATE SET
                    wave_height    = EXCLUDED.wave_height,
                    wave_period    = EXCLUDED.wave_period,
                    wave_direction = EXCLUDED.wave_direction,
                    wind_speed     = EXCLUDED.wind_speed,
                    wind_direction = EXCLUDED.wind_direction,
                    water_temp     = EXCLUDED.water_temp,
                    score          = EXCLUDED.score,
                    fetched_at     = NOW();
            """, (
                spot["id"], spot["name"], spot["state"], spot["city"],
                spot["lat"], spot["lon"],
                wave_height, wave_period, wave_dir,
                wind_speed, wind_dir, water_temp, score,
            ))

            # Salva dados horários de ondas para o gráfico de marés
            hourly = marine.get("hourly", {})
            times  = hourly.get("time", [])
            heights = hourly.get("wave_height", [])
            for t, h in zip(times, heights):
                if h is None:
                    continue
                cur.execute("""
                    INSERT INTO tide_data (spot_id, ts, tide_height)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (spot_id, ts) DO UPDATE SET tide_height = EXCLUDED.tide_height;
                """, (spot["id"], t, h))
        conn.commit()


def refresh_all_spots():
    for spot in SPOTS:
        if is_cache_stale(spot["id"]):
            try:
                marine = fetch_spot_data(spot)
                wind   = fetch_wind_data(spot)
                upsert_spot(spot, marine, wind)
            except (requests.RequestException, Exception) as exc:
                print(f"[WARN] Falha ao atualizar {spot['name']}: {exc}")


def get_all_spots():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT spot_id, name, state, city, lat, lon,
                       wave_height, wave_period, wave_direction,
                       wind_speed, wind_direction, water_temp, score,
                       fetched_at
                FROM surf_spots
                ORDER BY score DESC;
            """)
            return cur.fetchall()


def get_tide_data(spot_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ts, tide_height
                FROM tide_data
                WHERE spot_id = %s
                  AND ts >= NOW() - INTERVAL '12 hours'
                ORDER BY ts ASC
                LIMIT 48;
            """, (spot_id,))
            return cur.fetchall()


def get_total_visits():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visits;")
            return cur.fetchone()["total"]


def log_visit(path: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO visits (path) VALUES (%s);", (path,))
        conn.commit()
