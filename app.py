from flask import Flask, jsonify
import requests
import json
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

ESPN_TEAM_NAME_MAP = {
    "Brazil":"Brasil","Morocco":"Marruecos","Switzerland":"Suiza","Qatar":"Qatar",
    "Scotland":"Escocia","Haiti":"Haití","United States":"Estados Unidos",
    "Paraguay":"Paraguay","Mexico":"México","South Africa":"Sudáfrica",
    "South Korea":"Corea del Sur","Czech Republic":"Chequia","Czechia":"Chequia",
    "Canada":"Canadá","Bosnia and Herzegovina":"Bosnia y Herzegovina",
    "Australia":"Australia","Turkey":"Turquía","Netherlands":"Países Bajos",
    "Japan":"Japón","Tunisia":"Túnez","Sweden":"Suecia","Belgium":"Bélgica",
    "Egypt":"Egipto","Iran":"Irán","New Zealand":"Nueva Zelanda","Spain":"España",
    "Cape Verde":"Cabo Verde","Saudi Arabia":"Arabia Saudita","Uruguay":"Uruguay",
    "France":"Francia","Senegal":"Senegal","Norway":"Noruega","Iraq":"Irak",
    "Argentina":"Argentina","Algeria":"Argelia","Austria":"Austria",
    "Jordan":"Jordania","Portugal":"Portugal","Uzbekistan":"Uzbekistán",
    "Colombia":"Colombia","DR Congo":"RD Congo","England":"Inglaterra",
    "Croatia":"Croacia","Ghana":"Ghana","Panama":"Panamá","Germany":"Alemania",
    "Curacao":"Curazao","Ecuador":"Ecuador","Ivory Coast":"Costa de Marfil",
}

def fetch_espn_scores():
    """Scores en tiempo real desde ESPN"""
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        r.raise_for_status()
        events = r.json().get("events", [])
        scores = []
        for ev in events:
            comps = ev.get("competitions", [])
            if not comps: continue
            comp = comps[0]
            status = comp.get("status", {}).get("type", {}).get("name", "")
            # Solo partidos en juego o terminados
            if status not in ["STATUS_IN_PROGRESS", "STATUS_FINAL", "STATUS_HALFTIME"]:
                continue
            competitors = comp.get("competitors", [])
            if len(competitors) < 2: continue
            home = next((c for c in competitors if c.get("homeAway")=="home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway")=="away"), competitors[1])
            home_name = ESPN_TEAM_NAME_MAP.get(home.get("team",{}).get("displayName",""), home.get("team",{}).get("displayName",""))
            away_name = ESPN_TEAM_NAME_MAP.get(away.get("team",{}).get("displayName",""), away.get("team",{}).get("displayName",""))
            home_score = home.get("score","0")
            away_score = away.get("score","0")
            scores.append({
                "home": home_name,
                "away": away_name,
                "homeScore": int(home_score) if str(home_score).isdigit() else 0,
                "awayScore": int(away_score) if str(away_score).isdigit() else 0,
                "status": status
            })
        return scores
    except Exception as e:
        print(f"Error ESPN scores: {e}")
        return []

def fetch_openfootball():
    try:
        r = requests.get(OF_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        scorers = {}
        for m in data.get("matches", []):
            if not m.get("score") or not m["score"].get("ft"):
                continue
            ga, gb = m["score"]["ft"]
            team_a = es(m.get("team1", ""))
            team_b = es(m.get("team2", ""))
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
        return sorted(scorers.values(), key=lambda x: -x["total"])[:15]
    except Exception as e:
        print(f"Error openfootball: {e}")
        return []

@app.route("/stats")
def stats():
    goals_of = fetch_openfootball()
    scores = fetch_espn_scores()

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





# ── ESPN API - Alineaciones via ESPN internal API ──────────────────────────────
ESPN_TEAM_MAP = {
    "Brazil":"Brasil","Morocco":"Marruecos","Switzerland":"Suiza","Qatar":"Qatar",
    "Scotland":"Escocia","Haiti":"Haití","United States":"Estados Unidos",
    "Paraguay":"Paraguay","Mexico":"México","South Africa":"Sudáfrica",
    "South Korea":"Corea del Sur","Czech Republic":"Chequia",
    "Canada":"Canadá","Bosnia and Herzegovina":"Bosnia y Herzegovina",
    "Australia":"Australia","Turkey":"Turquía",
}

@app.route("/lineups")
def lineups():
    """Alineaciones de partidos del día vía ESPN"""
    try:
        # Obtener partidos del día
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        events = r.json().get("events", [])
        result = []
        for ev in events:
            eid = ev.get("id")
            ename = ev.get("name","")
            # Obtener alineaciones
            lr = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={eid}",
                timeout=10
            )
            if not lr.ok:
                continue
            ld = lr.json()
            rosters = ld.get("rosters", [])
            teams = []
            for roster in rosters:
                team_name = roster.get("team",{}).get("displayName","")
                team_es = ESPN_TEAM_MAP.get(team_name, team_name)
                starters = []
                bench = []
                for p in roster.get("roster", []):
                    name = p.get("athlete",{}).get("displayName","")
                    jersey = p.get("jersey","")
                    pos = p.get("position",{}).get("abbreviation","")
                    starter = p.get("starter", False)
                    subbed_in = p.get("subbedIn", False)
                    subbed_out = p.get("subbedOut", False)
                    player = {"name": name, "jersey": jersey, "pos": pos,
                              "subbedIn": subbed_in, "subbedOut": subbed_out}
                    if starter:
                        starters.append(player)
                    else:
                        bench.append(player)
                teams.append({"team": team_es, "starters": starters, "bench": bench})
            result.append({"eventId": eid, "name": ename, "teams": teams})
        resp = jsonify(result)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug_espn_stats/<event_id>")
def debug_espn_stats(event_id):
    """Ver estadísticas del boxscore de ESPN"""
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
            timeout=10
        )
        d = r.json()
        boxscore = d.get("boxscore", {})
        return f"<pre>{json.dumps(boxscore, indent=2, ensure_ascii=False)[:5000]}</pre>"
    except Exception as e:
        return f"Error: {e}"


    """Buscar event IDs del Mundial en ESPN"""
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        events = r.json().get("events", [])
        result = [{"id": e.get("id"), "name": e.get("name"), "date": e.get("date")} for e in events]
        return f"Status: {r.status_code}<br><pre>{json.dumps(result, indent=2, ensure_ascii=False)}</pre>"
    except Exception as e:
        return f"Error: {e}"

@app.route("/debug_espn_lineup/<event_id>")
def debug_espn_lineup(event_id):
    """Ver alineaciones de un partido ESPN"""
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
            timeout=10
        )
        d = r.json()
        keys = list(d.keys())
        rosters = d.get("rosters", [])
        boxscore = d.get("boxscore", {})
        return f"Status: {r.status_code}<br>Keys: {keys}<br>Rosters count: {len(rosters)}<br><pre>{json.dumps(rosters[:1] if rosters else boxscore, indent=2, ensure_ascii=False)[:3000]}</pre>"
    except Exception as e:
        return f"Error: {e}"
