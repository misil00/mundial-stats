from flask import Flask, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

SOFASCORE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com"
}

# Mundial 2026 en SofaScore: tournament 16, season a buscar
TOURNAMENT_ID = 16

def get_season_id():
    try:
        r = requests.get(
            f"https://api.sofascore.com/api/v1/unique-tournament/{TOURNAMENT_ID}/seasons",
            headers=SOFASCORE_HEADERS, timeout=10
        )
        seasons = r.json().get("seasons", [])
        # Buscar temporada 2026
        for s in seasons:
            if "2026" in str(s.get("year", "")) or "2026" in str(s.get("name", "")):
                return s["id"]
        return seasons[0]["id"] if seasons else None
    except Exception as e:
        print(f"Error getting season: {e}")
        return None

def get_top_scorers(season_id):
    try:
        r = requests.get(
            f"https://api.sofascore.com/api/v1/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/top-players/scoring",
            headers=SOFASCORE_HEADERS, timeout=10
        )
        players = r.json().get("topPlayers", [])
        return [
            {
                "jugador": p.get("player", {}).get("name", ""),
                "seleccion": p.get("team", {}).get("name", ""),
                "total": p.get("statistics", {}).get("goals", 0)
            }
            for p in players[:15]
        ]
    except Exception as e:
        print(f"Error scorers: {e}")
        return []

def get_results(season_id):
    try:
        r = requests.get(
            f"https://api.sofascore.com/api/v1/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/last/0",
            headers=SOFASCORE_HEADERS, timeout=10
        )
        events = r.json().get("events", [])
        results = []
        for e in events:
            if e.get("status", {}).get("type") != "finished":
                continue
            results.append({
                "home": e.get("homeTeam", {}).get("name", ""),
                "away": e.get("awayTeam", {}).get("name", ""),
                "homeScore": e.get("homeScore", {}).get("current", ""),
                "awayScore": e.get("awayScore", {}).get("current", "")
            })
        return results
    except Exception as e:
        print(f"Error results: {e}")
        return []

@app.route("/stats")
def stats():
    season_id = get_season_id()
    result = {
        "goals": [],
        "assists": [],
        "yellowCards": [],
        "redCards": [],
        "cleanSheets": [],
        "saves": [],
        "scores": [],
        "seasonId": season_id,
        "updated": datetime.utcnow().isoformat() + "Z"
    }

    if season_id:
        result["goals"] = get_top_scorers(season_id)
        result["scores"] = get_results(season_id)

    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/")
def index():
    return "Mundial 2026 Stats API OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
