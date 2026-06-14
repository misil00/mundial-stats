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
DEPLOY_HOOK = "https://api.render.com/deploy/srv-d8mn42m7r5hc73a0cs20?key=kJ1QEv1G3Qw"

MARCA_BASE = "https://api.unidadeditorial.es/sports/v1/player-total-rank/sport/01/tournament/0117/season/2025"

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
}

def es(name):
    return NAME_MAP.get(name, name)

def fetch_marca_rank(sort_by):
    """Fetch ranking from Marca internal API"""
    try:
        url = f"{MARCA_BASE}/sort/{sort_by}?site=2&mn=50"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("rank", [])
    except Exception as e:
        print(f"Error Marca {sort_by}: {e}")
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

    # Tarjetas desde Marca
    cards_rank = fetch_marca_rank("cards")
    yellow = []
    red = []
    for p in cards_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        yc = p.get("cards", 0) - p.get("redCards", 0)  # amarillas = total - rojas
        rc = p.get("redCards", 0)
        if yc > 0:
            yellow.append({"jugador": name, "seleccion": team, "total": yc})
        if rc > 0:
            red.append({"jugador": name, "seleccion": team, "total": rc})

    # Goles desde Marca
    goals_rank = fetch_marca_rank("goals")
    goals_marca = []
    for p in goals_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        total = p.get("goals", 0)
        if name and total > 0:
            goals_marca.append({"jugador": name, "seleccion": team, "total": total})

    # Asistencias desde Marca
    assists_rank = fetch_marca_rank("assists")
    assists = []
    for p in assists_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        total = p.get("assists", 0)
        if name and total > 0:
            assists.append({"jugador": name, "seleccion": team, "total": total})

    # Porteros invictos desde Marca
    saves_rank = fetch_marca_rank("saves")
    saves = []
    clean = []
    for p in saves_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        sv = p.get("saves", 0)
        gc = p.get("goalsConceded", 0)
        if name and sv > 0:
            saves.append({"jugador": name, "seleccion": team, "total": sv})
        if name and gc == 0 and p.get("games", 0) > 0:
            clean.append({"jugador": name, "seleccion": team, "total": p.get("games", 1)})

    goals = goals_marca if goals_marca else goals_of

    result = {
        "goals": goals,
        "assists": assists,
        "yellowCards": yellow,
        "redCards": red,
        "cleanSheets": clean,
        "saves": saves,
        "scores": scores,
        "updated": datetime.utcnow().isoformat() + "Z"
    }

    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/debug")
def debug():
    try:
        r = requests.get(f"{MARCA_BASE}/sort/cards?site=2&mn=50", headers=HEADERS, timeout=10)
        return f"Status: {r.status_code}<br>Data: {r.text[:2000]}"
    except Exception as e:
        return f"Error: {e}"

@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats /debug"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


# ── BALLDONTLIE - Alineaciones ────────────────────────────────────────────────
BDL_KEY = "58dc8429-9e2a-4ed9-9343-c036853ac116"
BDL_HEADERS = {"Authorization": BDL_KEY}
BDL_BASE = "https://api.balldontlie.io/fifa/worldcup/v1"

@app.route("/lineups")
def lineups():
    """Alineaciones de todos los partidos jugados"""
    try:
        # Primero obtener los partidos
        r = requests.get(f"{BDL_BASE}/matches", headers=BDL_HEADERS, timeout=10)
        r.raise_for_status()
        matches = r.json().get("data", [])
        
        result = []
        for m in matches:
            mid = m.get("id")
            status = m.get("status","")
            if status not in ["finished","live","in_progress"]:
                continue
            # Alineaciones del partido
            lr = requests.get(f"{BDL_BASE}/match_lineups", 
                             params={"match_ids[]": mid},
                             headers=BDL_HEADERS, timeout=10)
            if not lr.ok:
                continue
            result.append({
                "match_id": mid,
                "home": m.get("home_team",{}).get("name",""),
                "away": m.get("away_team",{}).get("name",""),
                "lineups": lr.json().get("data",[])
            })
        
        response = jsonify(result)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug_bdl")
def debug_bdl():
    """Ver respuesta cruda de BallDontLie"""
    try:
        r = requests.get(f"{BDL_BASE}/matches", headers=BDL_HEADERS, timeout=10)
        return f"Status: {r.status_code}<br>{r.text[:3000]}"
    except Exception as e:
        return f"Error: {e}"
