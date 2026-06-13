from flask import Flask, jsonify
import requests

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
    "Accept": "application/json"
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"

def fetch_espn_leaders():
    try:
        r = requests.get(f"{ESPN_BASE}/leaders", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error ESPN leaders: {e}")
        return {}

def fetch_espn_scoreboard():
    try:
        r = requests.get(f"{ESPN_BASE}/scoreboard?limit=200", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error ESPN scoreboard: {e}")
        return {}

@app.route("/stats")
def stats():
    result = {
        "goals": [],
        "assists": [],
        "yellowCards": [],
        "redCards": [],
        "cleanSheets": [],
        "saves": [],
        "scores": []
    }

    # Estadísticas desde ESPN leaders
    leaders_data = fetch_espn_leaders()
    for cat in leaders_data.get("categories", []):
        name = (cat.get("name") or "").lower()
        athletes = []
        for leader in cat.get("leaders", []):
            for a in leader.get("athletes", []):
                athletes.append({
                    "jugador": a.get("athlete", {}).get("displayName", ""),
                    "seleccion": a.get("team", {}).get("displayName", ""),
                    "total": float(a.get("value", 0))
                })
        if not athletes:
            continue
        if "goal" in name and "conceded" not in name:
            result["goals"] = athletes
        elif "assist" in name:
            result["assists"] = athletes
        elif "yellow" in name:
            result["yellowCards"] = athletes
        elif "red" in name:
            result["redCards"] = athletes
        elif "clean" in name or "shutout" in name:
            result["cleanSheets"] = athletes
        elif "save" in name:
            result["saves"] = athletes

    # Scores desde ESPN scoreboard
    scoreboard = fetch_espn_scoreboard()
    for ev in scoreboard.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed"):
            continue
        teams = comp.get("competitors", [])
        if len(teams) < 2:
            continue
        home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
        away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
        result["scores"].append({
            "home": home.get("team", {}).get("displayName", ""),
            "away": away.get("team", {}).get("displayName", ""),
            "homeScore": home.get("score", ""),
            "awayScore": away.get("score", "")
        })

    from datetime import datetime
    result["updated"] = datetime.utcnow().isoformat() + "Z"

    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
