from flask import Flask, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
    "Referer": "https://www.365scores.com/"
}

BASE = "https://webws.365scores.com/web/stats/?appTypeId=5&langId=2&timezoneName=America/New_York&userCountryId=6&competitions=5930&statsName="

STATS = {
    "goals":       "goals",
    "assists":     "assists", 
    "yellowCards": "yellowCards",
    "redCards":    "redCards",
    "cleanSheets": "cleanSheets",
    "saves":       "saves",
}

def fetch_stat(stat_name):
    try:
        r = requests.get(BASE + stat_name, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        stats = data.get("stats") or data.get("topStats") or []
        athletes = (stats[0] if stats else {}).get("athletes") or (stats[0] if stats else {}).get("topAthletes") or []
        return [
            {
                "jugador": a.get("name", ""),
                "seleccion": a.get("teamName") or a.get("competitorName", ""),
                "total": a.get("value", 0),
                "athleteId": a.get("athleteId", "")
            }
            for a in athletes[:20]
        ]
    except Exception as e:
        print(f"Error fetching {stat_name}: {e}")
        return []

@app.route("/stats")
def stats():
    result = {}
    for key, stat_name in STATS.items():
        result[key] = fetch_stat(stat_name)
    result["updated"] = datetime.utcnow().isoformat() + "Z"
    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
