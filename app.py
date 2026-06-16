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

MARCA_TEAM_BASE = "https://api.unidadeditorial.es/sports/v1/team-total-rank/sport/01/tournament/0117/season/2025"

def fetch_marca_team_rank(sort_by):
    """Fetch TEAM ranking from Marca - one row per team"""
    try:
        url = f"{MARCA_TEAM_BASE}/sort/{sort_by}?site=2&mn=50"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("rank", [])
    except Exception as e:
        print(f"Error Marca team {sort_by}: {e}")
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
    # Si el cache está vacío, recapturar todo
    if not _cache.get("scores"):
        try:
            _auto_capture()
        except:
            pass
    # Auto-capturar partidos finalizados de hoy que no estén en cache
    try:
        for ev in scores:
            if ev.get("status") in ["STATUS_FINAL","STATUS_FULL_TIME"]:
                eid = ev.get("eventId")
                if eid and not _cache["scores"].get(eid):
                    edata = fetch_espn_event_full(eid)
                    if edata and edata.get("teams_score"):
                        _cache["lineups"][eid] = edata
                        _cache["scores"][eid] = {}
                        for t in edata["teams_score"]:
                            _cache["scores"][eid][t["homeAway"]] = {
                                "team": t["team"], "score": t["score"],
                                "winner": t["winner"], "status": edata.get("status",""),
                                "date": edata.get("date","")
                            }
    except:
        pass

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

    # Equipos desde Marca - endpoint de EQUIPOS (una fila por equipo)
    equipos_rank = fetch_marca_team_rank("passes")
    equipos_dict = {}
    for p in equipos_rank:
        team = es(p.get("teamName", ""))
        if not team or team in equipos_dict:
            continue
        equipos_dict[team] = {
            "seleccion": team,
            "gf": p.get("goalsFor", p.get("goals", 0)),
            "gc": p.get("goalsAgainst", p.get("goalsConceded", 0)),
            "disparos": p.get("shots", p.get("totalShots", 0)),
            "faltas": p.get("foulsCommitted", p.get("fouls", 0)),
            "ta": p.get("yellowCards", 0),
            "tr": p.get("redCards", 0)
        }
    equipos = sorted(equipos_dict.values(), key=lambda e: (-(e["gf"] or 0), e["gc"] or 0))

    goals = goals_marca if goals_marca else goals_of

    # Scores: combinar stored + live ESPN
    stored_data = get_cache()
    stored_scores_list = []
    for eid, sides in stored_data.get("scores", {}).items():
        home = sides.get("home", {})
        away = sides.get("away", {})
        if home and away and home.get("score","") != "" and away.get("score","") != "":
            stored_scores_list.append({
                "home": home.get("team",""),
                "away": away.get("team",""),
                "homeScore": home.get("score",""),
                "awayScore": away.get("score",""),
                "status": home.get("status",""),
                "eventId": eid
            })

    # Agregar scores en vivo que no estén ya guardados
    live_keys = {f"{s['home']}_{s['away']}" for s in scores}
    stored_keys = {f"{s['home']}_{s['away']}" for s in stored_scores_list}
    all_scores = stored_scores_list + [s for s in scores if f"{s['home']}_{s['away']}" not in stored_keys]

    # Auto-guardar scores en vivo que sean FINAL
    changed = False
    for s in scores:
        if s.get("status") == "STATUS_FINAL" or s.get("status") == "STATUS_FULL_TIME":
            # Buscar el eventId correspondiente
            for eid, sides in stored_data.get("scores", {}).items():
                h = sides.get("home", {})
                a = sides.get("away", {})
                if h.get("team") == s["home"] and a.get("team") == s["away"]:
                    break
            else:
                changed = True
    if changed:
        try:
            _auto_capture()
        except:
            pass

    result = {
        "goals": goals,
        "assists": assists,
        "yellowCards": yellow,
        "redCards": red,
        "cleanSheets": clean,
        "saves": saves,
        "equipos": equipos,
        "scores": all_scores,
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

@app.route("/debug_espn_score/<event_id>")
def debug_espn_score(event_id):
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
            timeout=10
        )
        d = r.json()
        header = d.get("header", {})
        comps = header.get("competitions", [])
        result = []
        for comp in comps:
            for team in comp.get("competitors", []):
                result.append({
                    "team": team.get("team", {}).get("displayName",""),
                    "score": team.get("score",""),
                    "homeAway": team.get("homeAway",""),
                    "winner": team.get("winner", False)
                })
        return f"<pre>{json.dumps(result, indent=2, ensure_ascii=False)}</pre>"
    except Exception as e:
        return f"Error: {e}"

@app.route("/debug_espn_stats/<event_id>")
def debug_espn_stats(event_id):
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
            timeout=10
        )
        d = r.json()
        boxscore = d.get("boxscore", {})
        keys = list(boxscore.keys())
        teams = boxscore.get("teams", [])
        players = boxscore.get("players", [])
        return f"<b>Keys boxscore:</b> {keys}<br><br><b>Teams stats:</b><pre>{json.dumps(teams, indent=2, ensure_ascii=False)[:4000]}</pre>"
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


# ── STATS POR PARTIDO (ESPN) ───────────────────────────────────────────────────
@app.route("/match_stats")
def match_stats():
    """Estadísticas por partido del día vía ESPN boxscore"""
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        events = r.json().get("events", [])
        result = []
        for ev in events:
            eid = ev.get("id")
            ename = ev.get("name","")
            sr = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={eid}",
                timeout=10
            )
            if not sr.ok: continue
            boxscore = sr.json().get("boxscore", {})
            teams_data = []
            for t in boxscore.get("teams", []):
                team_name = ESPN_TEAM_NAME_MAP.get(t.get("team",{}).get("displayName",""), t.get("team",{}).get("displayName",""))
                stats = {}
                for s in t.get("statistics", []):
                    stats[s["name"]] = s["displayValue"]
                teams_data.append({"team": team_name, "stats": stats})
            result.append({"eventId": eid, "name": ename, "teams": teams_data})
        resp = jsonify(result)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── RATING POR JUGADOR (Marca cruzado) ────────────────────────────────────────
@app.route("/rating")
def rating():
    """Rating de jugadores basado en datos de Marca - estilo Sorare"""
    try:
        goals_rank   = fetch_marca_rank("goals")
        assists_rank = fetch_marca_rank("assists")
        cards_rank   = fetch_marca_rank("cards")
        saves_rank   = fetch_marca_rank("saves")

        players = {}

        def get_or_create(name, team):
            key = f"{name}|{team}"
            if key not in players:
                players[key] = {
                    "jugador": name, "seleccion": team,
                    "goles":0,"asistencias":0,"pases":0,
                    "amarillas":0,"rojas":0,"atajadas":0,
                    "porteria_invicta":0,"partidos":0
                }
            return players[key]

        for p in goals_rank:
            name = p.get("knownName") or p.get("playerName","")
            team = es(p.get("teamName",""))
            if not name: continue
            pl = get_or_create(name, team)
            pl["goles"] = p.get("goals",0)
            pl["asistencias"] = p.get("assists",0)
            pl["pases"] = p.get("successPasses",0)
            pl["partidos"] = p.get("games",0)

        for p in assists_rank:
            name = p.get("knownName") or p.get("playerName","")
            team = es(p.get("teamName",""))
            if not name: continue
            pl = get_or_create(name, team)
            pl["asistencias"] = max(pl["asistencias"], p.get("assists",0))
            pl["pases"] = max(pl["pases"], p.get("successPasses",0))
            if not pl["partidos"]: pl["partidos"] = p.get("games",0)

        for p in cards_rank:
            name = p.get("knownName") or p.get("playerName","")
            team = es(p.get("teamName",""))
            if not name: continue
            pl = get_or_create(name, team)
            pl["amarillas"] = p.get("cards",0) - p.get("redCards",0)
            pl["rojas"] = p.get("redCards",0)
            if not pl["partidos"]: pl["partidos"] = p.get("games",0)

        for p in saves_rank:
            name = p.get("knownName") or p.get("playerName","")
            team = es(p.get("teamName",""))
            if not name: continue
            pl = get_or_create(name, team)
            pl["atajadas"] = p.get("saves",0)
            gc = p.get("goalsConceded",0)
            games = p.get("games",0)
            pl["porteria_invicta"] = 1 if gc == 0 and games > 0 else 0
            if not pl["partidos"]: pl["partidos"] = games

        # Calcular rating estilo Sorare (base 35, escala 0-100)
        rated = []
        for key, pl in players.items():
            base = 35
            # Positivos
            base += pl["goles"] * 15
            base += pl["asistencias"] * 10
            base += min(pl["pases"] * 0.05, 10)  # max 10 pts por pases
            base += pl["atajadas"] * 2
            base += pl["porteria_invicta"] * 10
            # Negativos
            base -= pl["amarillas"] * 3
            base -= pl["rojas"] * 10
            # Normalizar 0-100
            rating_val = max(0, min(100, base))
            # Solo mostrar si tiene alguna acción
            if pl["goles"] or pl["asistencias"] or pl["atajadas"] or pl["porteria_invicta"]:
                rated.append({
                    "jugador": pl["jugador"],
                    "seleccion": pl["seleccion"],
                    "rating": round(rating_val, 1),
                    "goles": pl["goles"],
                    "asistencias": pl["asistencias"],
                    "pases": pl["pases"],
                    "amarillas": pl["amarillas"],
                    "rojas": pl["rojas"],
                    "atajadas": pl["atajadas"],
                    "partidos": pl["partidos"]
                })

        rated.sort(key=lambda x: -x["rating"])
        resp = jsonify(rated[:50])
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── PERSISTENCIA DE DATOS ESPN + MARCA ────────────────────────────────────────
import os

# ── IN-MEMORY CACHE (persiste mientras el servidor está vivo) ─────────────────
_cache = {"scores": {}, "lineups": {}, "initialized": False}

# ESPN team IDs for FIFA World Cup 2026
ESPN_TEAM_IDS = {
    "Argelia":624,"Argentina":202,"Australia":628,"Austria":474,
    "Bélgica":459,"Bosnia y Herzegovina":452,"Brasil":205,"Canadá":206,
    "Cabo Verde":2597,"Colombia":208,"RD Congo":2850,"Croacia":477,
    "Curazao":11678,"Chequia":450,"Ecuador":209,"Egipto":2620,
    "Inglaterra":448,"Francia":478,"Alemania":481,"Ghana":4469,
    "Haití":2654,"Irán":469,"Irak":4375,"Costa de Marfil":4789,
    "Japón":627,"Jordania":2917,"México":203,"Marruecos":2869,
    "Países Bajos":449,"Nueva Zelanda":2666,"Noruega":464,"Panamá":2659,
    "Paraguay":210,"Portugal":482,"Qatar":4398,"Arabia Saudita":655,
    "Escocia":580,"Senegal":654,"Sudáfrica":467,"Corea del Sur":451,
    "España":164,"Suecia":466,"Suiza":475,"Túnez":659,
    "Turquía":465,"Estados Unidos":660,"Uruguay":212,"Uzbekistán":2570
}

_squads_cache = {}
_espn_id_map = {}  # nombre ESPN -> id real, construido del scoreboard

SPANISH_TO_ESPN = {
    "México":"Mexico","Sudáfrica":"South Africa","Corea del Sur":"South Korea",
    "Chequia":"Czechia","Canadá":"Canada","Bosnia y Herzegovina":"Bosnia-Herzegovina",
    "Suiza":"Switzerland","Brasil":"Brazil","Marruecos":"Morocco","Haití":"Haiti",
    "Escocia":"Scotland","Estados Unidos":"USA","Australia":"Australia","Turquía":"Türkiye",
    "Alemania":"Germany","Curazao":"Curaçao","Costa de Marfil":"Ivory Coast","Ecuador":"Ecuador",
    "Países Bajos":"Netherlands","Japón":"Japan","Túnez":"Tunisia","Suecia":"Sweden",
    "Bélgica":"Belgium","Egipto":"Egypt","Irán":"Iran","Nueva Zelanda":"New Zealand",
    "España":"Spain","Cabo Verde":"Cape Verde","Arabia Saudita":"Saudi Arabia","Uruguay":"Uruguay",
    "Francia":"France","Senegal":"Senegal","Noruega":"Norway","Irak":"Iraq",
    "Argentina":"Argentina","Argelia":"Algeria","Austria":"Austria","Jordania":"Jordan",
    "Portugal":"Portugal","Uzbekistán":"Uzbekistan","Colombia":"Colombia","RD Congo":"DR Congo",
    "Inglaterra":"England","Croacia":"Croatia","Ghana":"Ghana","Panamá":"Panama",
    "Paraguay":"Paraguay","Qatar":"Qatar"
}

def build_espn_id_map():
    """Construye mapa nombre->id real desde ESPN (lista completa de equipos + scoreboard)"""
    global _espn_id_map
    # 1. Lista completa de equipos del torneo (todos, hayan jugado o no)
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams?limit=100",
            timeout=10
        )
        if r.ok:
            data = r.json()
            sports = data.get("sports", [])
            for sport in sports:
                for league in sport.get("leagues", []):
                    for t in league.get("teams", []):
                        team = t.get("team", {})
                        tid = team.get("id")
                        name = team.get("displayName", "")
                        if tid and name:
                            _espn_id_map[name] = tid
    except:
        pass
    # 2. Scoreboard (respaldo para equipos que ya jugaron)
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        if r.ok:
            data = r.json()
            for ev in data.get("events", []):
                for comp in ev.get("competitions", []):
                    for c in comp.get("competitors", []):
                        team = c.get("team", {})
                        tid = team.get("id")
                        name = team.get("displayName", "")
                        if tid and name:
                            _espn_id_map[name] = tid
    except:
        pass

def fetch_espn_squad(team_name):
    global _squads_cache, _espn_id_map
    if team_name in _squads_cache:
        return _squads_cache[team_name]
    # 1. ID fijo verificado (los 48 equipos reales)
    team_id = ESPN_TEAM_IDS.get(team_name)
    # 2. Respaldo: buscar ID real dinámicamente
    if not team_id:
        if not _espn_id_map:
            build_espn_id_map()
        espn_name = SPANISH_TO_ESPN.get(team_name, team_name)
        team_id = _espn_id_map.get(espn_name) or _espn_id_map.get(team_name)
    if not team_id:
        return None
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams/{team_id}/roster"
        r = requests.get(url, timeout=10)
        if not r.ok:
            return None
        data = r.json()
        athletes = data.get("athletes", [])
        players = []
        for a in athletes:
            players.append({
                "jersey": a.get("jersey", ""),
                "name": a.get("displayName", a.get("fullName", "")),
                "pos": a.get("position", {}).get("abbreviation", ""),
                "posName": a.get("position", {}).get("displayName", "")
            })
        coach = data.get("coach", [])
        coach_name = ""
        if coach:
            c = coach[0]
            coach_name = f"{c.get('firstName','')} {c.get('lastName','')}".strip()
        if not players:
            return None
        result = {"players": players, "coach": coach_name}
        _squads_cache[team_name] = result
        return result
    except:
        return None

def get_cache():
    global _cache
    if not _cache["initialized"]:
        _auto_capture()
    return _cache

def _auto_capture():
    global _cache
    known_ids = [
        "760414","760415","760416","760417",
        "760418","760419","760420","760421",
        "760422","760423","760424","760425",
        "760426","760427","760428","760429","760430"
    ]
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        for ev in r.json().get("events", []):
            eid = ev.get("id")
            if eid and eid not in known_ids:
                known_ids.append(eid)
    except:
        pass

    for eid in known_ids:
        try:
            edata = fetch_espn_event_full(eid)
            if edata and edata.get("teams_score"):
                _cache["lineups"][eid] = edata
                _cache["scores"][eid] = {}
                for t in edata["teams_score"]:
                    _cache["scores"][eid][t["homeAway"]] = {
                        "team": t["team"], "score": t["score"],
                        "winner": t["winner"], "status": edata.get("status",""),
                        "date": edata.get("date","")
                    }
        except:
            pass
    _cache["initialized"] = True
    print(f"Cache initialized: {len(_cache['scores'])} events")



def fetch_espn_event_full(event_id):
    """Fetch everything ESPN gives for a single event"""
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
            timeout=15
        )
        if not r.ok:
            return None
        d = r.json()

        result = {"event_id": event_id, "updated": datetime.utcnow().isoformat()}

        # Score from header
        header = d.get("header", {})
        for comp in header.get("competitions", []):
            teams = []
            status = comp.get("status", {}).get("type", {}).get("name", "")
            result["status"] = status
            result["date"] = comp.get("date", "")
            for c in comp.get("competitors", []):
                team_name = ESPN_TEAM_NAME_MAP.get(c.get("team", {}).get("displayName", ""), c.get("team", {}).get("displayName", ""))
                teams.append({
                    "team": team_name,
                    "score": c.get("score", ""),
                    "homeAway": c.get("homeAway", ""),
                    "winner": c.get("winner", False)
                })
            result["teams_score"] = teams

        # Rosters / lineups
        rosters = d.get("rosters", [])
        result["rosters"] = []
        for roster in rosters:
            team_name = ESPN_TEAM_NAME_MAP.get(roster.get("team", {}).get("displayName", ""), roster.get("team", {}).get("displayName", ""))
            starters = []
            bench = []
            for p in roster.get("roster", []):
                player = {
                    "name": p.get("athlete", {}).get("displayName", ""),
                    "jersey": p.get("jersey", ""),
                    "pos": p.get("position", {}).get("abbreviation", ""),
                    "starter": p.get("starter", False),
                    "subbedIn": p.get("subbedIn", False),
                    "subbedOut": p.get("subbedOut", False),
                    "formationPlace": p.get("formationPlace", ""),
                    "stats": {s["name"]: s["displayValue"] for s in p.get("stats", [])}
                }
                if p.get("starter"):
                    starters.append(player)
                else:
                    bench.append(player)
            result["rosters"].append({
                "team": team_name,
                "starters": starters,
                "bench": bench
            })

        # Boxscore stats
        boxscore = d.get("boxscore", {})
        result["boxscore_teams"] = []
        for t in boxscore.get("teams", []):
            team_name = ESPN_TEAM_NAME_MAP.get(t.get("team", {}).get("displayName", ""), t.get("team", {}).get("displayName", ""))
            stats = {s["name"]: s["displayValue"] for s in t.get("statistics", [])}
            result["boxscore_teams"].append({"team": team_name, "stats": stats})

        # Form / last 5 games
        result["form"] = d.get("form", [])

        # Key events (goals, cards, subs)
        result["keyEvents"] = d.get("keyEvents", [])

        return result
    except Exception as e:
        print(f"Error fetching event {event_id}: {e}")
        return None

@app.route("/capture/<event_id>")
def capture_event(event_id):
    """Capture and store all ESPN data for an event"""
    data = get_cache()
    event_data = fetch_espn_event_full(event_id)
    if not event_data:
        return jsonify({"error": "Could not fetch event"}), 500
    data["lineups"][event_id] = event_data
    # Also store score separately for quick access
    if event_data.get("teams_score"):
        for t in event_data["teams_score"]:
            key = f"{event_id}_{t['homeAway']}"
            if not data["scores"].get(event_id):
                data["scores"][event_id] = {}
            data["scores"][event_id][t["homeAway"]] = {
                "team": t["team"],
                "score": t["score"],
                "winner": t["winner"],
                "status": event_data.get("status", ""),
                "date": event_data.get("date", "")
            }
        resp = jsonify({"ok": True, "event_id": event_id, "data": event_data})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/capture_all")
def capture_all():
    """Capture all events from ESPN scoreboard + known past event IDs"""
    stored = get_cache()

    # Known past event IDs (Day 1 and 2 of World Cup 2026)
    known_ids = [
        "760414", "760415", "760416", "760417",  # Day 1 guesses
        "760418", "760419", "760420",              # Day 2 confirmed
        "760421", "760422", "760423", "760424", "760425"  # Day 3
    ]

    # Also get today's events from scoreboard
    try:
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        for ev in r.json().get("events", []):
            eid = ev.get("id")
            if eid and eid not in known_ids:
                known_ids.append(eid)
    except:
        pass

    captured = []
    failed = []
    for eid in known_ids:
        event_data = fetch_espn_event_full(eid)
        if event_data and event_data.get("teams_score"):
            stored["lineups"][eid] = event_data
            stored["scores"][eid] = {}
            for t in event_data.get("teams_score", []):
                stored["scores"][eid][t["homeAway"]] = {
                    "team": t["team"],
                    "score": t["score"],
                    "winner": t["winner"],
                    "status": event_data.get("status", ""),
                    "date": event_data.get("date", "")
                }
            captured.append(eid)
        else:
            failed.append(eid)

        resp = jsonify({"captured": captured, "failed": failed, "total": len(captured)})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/stored_scores")
def stored_scores():
    """Return all stored scores"""
    data = get_cache()
    # Convert to list format matching what the app expects
    scores_list = []
    for eid, sides in data.get("scores", {}).items():
        home = sides.get("home", {})
        away = sides.get("away", {})
        if home and away and home.get("score", "") != "" and away.get("score", "") != "":
            scores_list.append({
                "eventId": eid,
                "home": home.get("team", ""),
                "away": away.get("team", ""),
                "homeScore": home.get("score", ""),
                "awayScore": away.get("score", ""),
                "status": home.get("status", ""),
                "date": home.get("date", "")
            })
    resp = jsonify(scores_list)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/debug_equipos")
def debug_equipos():
    """Ver datos crudos del endpoint de equipos de Marca"""
    raw = fetch_marca_team_rank("passes")
    return jsonify({"count": len(raw), "first": raw[0] if raw else None, "sample": raw[:3]})

@app.route("/debug_ids")
def debug_ids():
    """Ver el mapa de IDs reales de ESPN"""
    if not _espn_id_map:
        build_espn_id_map()
    return jsonify({"count": len(_espn_id_map), "ids": _espn_id_map})

@app.route("/all_squads")
def all_squads():
    """Devuelve TODOS los planteles de una vez - URL fija sin acentos"""
    result = {}
    for team_name in ESPN_TEAM_IDS.keys():
        data = fetch_espn_squad(team_name)
        if data and data.get("players"):
            result[team_name] = data
    return jsonify(result)

@app.route("/squad/<team_name>")
def squad(team_name):
    """Return official squad for a team from ESPN"""
    result = fetch_espn_squad(team_name)
    if result is None:
        resp = jsonify({"error": "Team not found or no data", "team": team_name})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 404
    resp = jsonify({"team": team_name, "players": result["players"], "coach": result["coach"]})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/stored_lineups")
def stored_lineups():
    """Return all stored lineups"""
    data = get_cache()
    result = []
    for eid, ev in data.get("lineups", {}).items():
        if ev.get("rosters"):
            result.append({
                "eventId": eid,
                "status": ev.get("status", ""),
                "date": ev.get("date", ""),
                "teams": [
                    {
                        "team": r["team"],
                        "starters": r["starters"],
                        "bench": r["bench"]
                    } for r in ev.get("rosters", [])
                ],
                "boxscore": ev.get("boxscore_teams", []),
                "keyEvents": ev.get("keyEvents", [])
            })
    resp = jsonify(result)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
