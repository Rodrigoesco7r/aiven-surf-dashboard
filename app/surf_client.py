def fetch_spot_data(spot: dict) -> dict:
    """Busca ondas, vento e temperatura da Open-Meteo Marine API."""
    url = "https://marine-api.open-meteo.com/v1/marine"

    params = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "current": [
            "wave_height",
            "wave_period",
            "wave_direction",
            "wind_wave_height",
            "wind_wave_period",
        ],
        "hourly": [
            "wave_height",
            "wave_period",
            "sea_level_pressure",
        ],
        "daily": [
            "wave_height_max",
            "wave_period_max",
        ],
        "timezone": "America/Sao_Paulo",
        "forecast_days": 1,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)

        if not resp.ok:
            print(f"[Open-Meteo] Erro HTTP {resp.status_code}")
            print(f"[Open-Meteo] Resposta: {resp.text}")

        resp.raise_for_status()

        return resp.json()

    except requests.RequestException as exc:
        print(f"[Open-Meteo] Falha na requisição: {exc}")
        raise
