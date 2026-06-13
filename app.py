from flask import Flask, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://us.marca.com/"
}

OF_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

# APIs internas de Marca/Unidad Editorial
MARCA_BASE = "https://api.unidadeditorial.es/sports/v1/player-total-rank/sport/01/tournament/0117/season/2025"
MARCA_CARDS  = f"{MARCA_BASE}/sort/cards?site=2&mn=50"
MARCA_GOALS  = f"{MARCA_BASE}/sort/goals?site=2&mn=50"
MARCA_ASSISTS = f"{MARCA_BASE}/sort/assists?site=2&mn=50"
MARCA_SAVES  = f"{MARCA_BASE}/sort/saves?site=2&mn=50"

NAME_MAP = {
    "Mexico":"México","South Africa":"Sudáfrica","South Korea":"Corea del Sur",
    "Czech Republic":"Chequia","Canada":"Canadá","Switzerland":"Suiza",
    "Bosnia-Herzegovina":"Bosnia y Herzegovina","Bosnia & Herzegovina":"Bosnia y Herzegovina",
    "United States":"Estados Unidos","USA":"Estados Unidos",
    "Australia":"Australia","Turkey":"Turquía","Haiti":"Haití","Scotland":"Escocia",
    "Brazil":"Brasil","Morocco":"Marruecos","Netherlands":"Países Bajos","Japan":"Japón",
    "Tunisia":"Túnez","Sweden":"Suecia","Belgium":"Bélgica","Egypt":"Egipto",
    "Iran":"Irán","New Zealand":"Nueva Zelanda","Spain":"España","Cape Verde":"Cabo Verde",
    "Saudi Arabia":"Arabia Saudita","Uruguay":"Uruguay","France":"Francia",
    "Senegal":"Senegal","Norway":"Noruega","Iraq":"Irak","Argentina":"Argentina",
    "Algeria":"Argelia","Austria":"Austria","Jordan":"Jordania","Portugal":"Portugal",
    "Uzbekistan":"Uzbekistán","Colombia":"Colombia","DR Congo":"RD Congo",
    "England":"Inglaterra","Croatia":"Croacia","Ghana":"Ghana","Panama":"Panamá",
    "Germany":"Alemania","Curacao":"Curazao","Ecuador":"Ecuador",
    "Ivory Coast":"Costa de Marfil","Paraguay":"Paraguay","Qatar":"Qatar",
    "República Checa":"Chequia","Bosnia Herzegovina":"Bosnia y Herzegovina",
    "Estados Unidos":"Estados Unidos","Corea del Sur":"Corea del Sur"
}

def es(name):
    return NAME_MAP.get(name, name)

def fetch_marca(url, value_key):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        players = data.get("data", data.get("players", data.get("items", [])))
        result = []
        for p in players:
            name = p.get("playerName") or p.get("name") or p.get("player", {}).get("name", "")
            team = p.get("teamName") or p.get("team") or p.get("competitorName", "")
            value = p.get(value_key) or p.get("value") or p.get("total", 0)
            if name:
                result.append({"jugador": name, "seleccion": es(team), "total": int(value or 0)})
        return result[:15]
    except Exception as e:
        print(f"Error Marca {url}: {e}")
        return []

def fetch_openfootball():
    try:
        r = requests.get(OF_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        scorers = {}
        scores = []
        for m in data.get("matches", []):
            if not m.get("score") or not m["score"].get("ft"):
                continue
            ga, gb = m["score"]["ft"]
            team_a = es(m.get("team1", ""))
            team_b = es(m.get("team2", ""))
            scores.append({"home": team_a, "away": team_b, "homeScore": ga, "awayScore": gb})
            for g in m.get("goals1", []):
                name = g.get("name", "")
                if not name: continue
                key = f"{name}|{team_a}"
                if key not in scorers:
                    scorers[key] = {"jugador": name, "seleccion": team_a, "total": 0}
                scorers[key]["total"] += 1
            for g in m.get("goals2", []):
                name = g.get("name", "")
                if not name: continue
                key = f"{name}|{team_b}"
                if key not in scorers:
                    scorers[key] = {"jugador": name, "seleccion": team_b, "total": 0}
                scorers[key]["total"] += 1
        return sorted(scorers.values(), key=lambda x: -x["total"])[:15], scores
    except Exception as e:
        print(f"Error openfootball: {e}")
        return [], []

@app.route("/stats")
def stats():
    goals_of, scores = fetch_openfootball()
    
    # Intentar API de Marca para estadísticas
    cards_data = fetch_marca(MARCA_CARDS, "yellowCards")
    goals_marca = fetch_marca(MARCA_GOALS, "goals")
    assists = fetch_marca(MARCA_ASSISTS, "assists")
    saves = fetch_marca(MARCA_SAVES, "saves")
    
    # Separar amarillas y rojas de cards_data
    yellow = []
    red = []
    for p in cards_data:
        # La API de tarjetas tiene TA y TR
        if p.get("total", 0) > 0:
            yellow.append(p)

    # Usar goles de Marca si hay, sino openfootball
    goals = goals_marca if goals_marca else goals_of

    result = {
        "goals": goals,
        "assists": assists,
        "yellowCards": yellow,
        "redCards": red,
        "cleanSheets": [],
        "saves": saves,
        "scores": scores,
        "updated": datetime.utcnow().isoformat() + "Z"
    }

    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/debug")
def debug():
    """Ver respuesta cruda de la API de Marca"""
    try:
        r = requests.get(MARCA_CARDS, headers=HEADERS, timeout=10)
        return f"Status: {r.status_code}<br>Data: {r.text[:2000]}"
    except Exception as e:
        return f"Error: {e}"

@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats /debug"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
