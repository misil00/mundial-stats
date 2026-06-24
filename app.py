from flask import Flask, jsonify
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://us.marca.com/"
}

MARCA_BASE = "https://api.unidadeditorial.es/sports/v1/player-total-rank/sport/01/tournament/0117/season/2025"
OF_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

# ── Mapas de nombres ──────────────────────────────────────────────────────────
NAME_MAP = {
    "Mexico":"México","South Africa":"Sudáfrica","South Korea":"Corea del Sur",
    "Czech Republic":"Chequia","Czechia":"Chequia","Canada":"Canadá",
    "Switzerland":"Suiza","Bosnia-Herzegovina":"Bosnia y Herzegovina",
    "Bosnia & Herzegovina":"Bosnia y Herzegovina",
    "Bosnia and Herzegovina":"Bosnia y Herzegovina",
    "United States":"Estados Unidos","USA":"Estados Unidos",
    "Australia":"Australia","Turkey":"Turquía","Türkiye":"Turquía",
    "Haiti":"Haití","Scotland":"Escocia","Brazil":"Brasil","Morocco":"Marruecos",
    "Netherlands":"Países Bajos","Japan":"Japón","Tunisia":"Túnez","Sweden":"Suecia",
    "Belgium":"Bélgica","Egypt":"Egipto","Iran":"Irán","New Zealand":"Nueva Zelanda",
    "Spain":"España","Cape Verde":"Cabo Verde","Saudi Arabia":"Arabia Saudita",
    "Uruguay":"Uruguay","France":"Francia","Senegal":"Senegal","Norway":"Noruega",
    "Iraq":"Irak","Argentina":"Argentina","Algeria":"Argelia","Austria":"Austria",
    "Jordan":"Jordania","Portugal":"Portugal","Uzbekistan":"Uzbekistán",
    "Colombia":"Colombia","DR Congo":"RD Congo","Congo DR":"RD Congo",
    "England":"Inglaterra","Croatia":"Croacia","Ghana":"Ghana","Panama":"Panamá",
    "Germany":"Alemania","Curacao":"Curazao","Curaçao":"Curazao",
    "Ecuador":"Ecuador","Ivory Coast":"Costa de Marfil","Paraguay":"Paraguay",
    "Qatar":"Qatar","República Checa":"Chequia","Serbia":"Serbia",
}

def es(name):
    return NAME_MAP.get(name, name)

# ── PERSISTENCIA EN DISCO ─────────────────────────────────────────────────────
CACHE_FILE = "/tmp/mundial_cache.json"

def load_disk_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"scores": {}, "lineups": {}}

def save_disk_cache(data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving cache: {e}")

_cache = None

def get_cache():
    global _cache
    if _cache is None:
        _cache = load_disk_cache()
        # Si está vacío, capturar todo
        if not _cache.get("lineups"):
            capture_all_events()
    return _cache

def set_cache(data):
    global _cache
    _cache = data
    save_disk_cache(data)

# ── CAPTURA DE TODOS LOS EVENTOS ──────────────────────────────────────────────
def get_all_event_ids():
    """Obtiene todos los IDs de eventos del Mundial desde el inicio hasta hoy"""
    ids = set()
    try:
        # Rango completo del torneo
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
            "?dates=20260611-20260719&limit=950",
            timeout=15
        )
        if r.ok:
            for ev in r.json().get("events", []):
                eid = ev.get("id")
                if eid:
                    ids.add(eid)
    except Exception as e:
        print(f"Error getting all event IDs: {e}")
    # También scoreboard de hoy como respaldo
    try:
        r2 = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        if r2.ok:
            for ev in r2.json().get("events", []):
                eid = ev.get("id")
                if eid:
                    ids.add(eid)
    except:
        pass
    return list(ids)

def fetch_espn_event_full(event_id):
    """Fetch todo lo que ESPN da para un evento"""
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
            timeout=15
        )
        if not r.ok:
            return None
        d = r.json()

        result = {"event_id": event_id, "updated": datetime.utcnow().isoformat()}

        # Score del header
        header = d.get("header", {})
        for comp in header.get("competitions", []):
            status = comp.get("status", {}).get("type", {}).get("name", "")
            result["status"] = status
            result["date"] = comp.get("date", "")
            teams = []
            for c in comp.get("competitors", []):
                team_name = es(c.get("team", {}).get("displayName", ""))
                teams.append({
                    "team": team_name,
                    "score": c.get("score", ""),
                    "homeAway": c.get("homeAway", ""),
                    "winner": c.get("winner", False)
                })
            result["teams_score"] = teams

        # Rosters / alineaciones
        rosters = d.get("rosters", [])
        result["rosters"] = []
        for roster in rosters:
            team_name = es(roster.get("team", {}).get("displayName", ""))
            starters, bench = [], []
            for p in roster.get("roster", []):
                player = {
                    "name": p.get("athlete", {}).get("displayName", ""),
                    "jersey": p.get("jersey", ""),
                    "pos": p.get("position", {}).get("abbreviation", ""),
                    "subbedIn": p.get("subbedIn", False),
                    "subbedOut": p.get("subbedOut", False),
                }
                if p.get("starter"):
                    starters.append(player)
                else:
                    bench.append(player)
            if starters or bench:
                result["rosters"].append({"team": team_name, "starters": starters, "bench": bench})

        # Boxscore
        boxscore = d.get("boxscore", {})
        result["boxscore_teams"] = []
        for t in boxscore.get("teams", []):
            team_name = es(t.get("team", {}).get("displayName", ""))
            stats = {s["name"]: s["displayValue"] for s in t.get("statistics", [])}
            result["boxscore_teams"].append({"team": team_name, "stats": stats})

        return result
    except Exception as e:
        print(f"Error fetching event {event_id}: {e}")
        return None

def capture_all_events():
    """Captura todos los eventos finalizados del Mundial"""
    data = get_cache() if _cache else {"scores": {}, "lineups": {}}
    ids = get_all_event_ids()
    captured = 0
    for eid in ids:
        # Si ya está en cache y está finalizado, no re-capturar
        existing = data["lineups"].get(eid, {})
        if existing.get("status") in ["STATUS_FINAL", "STATUS_FULL_TIME"]:
            continue
        ev = fetch_espn_event_full(eid)
        if not ev or not ev.get("teams_score"):
            continue
        data["lineups"][eid] = ev
        data["scores"][eid] = {}
        for t in ev["teams_score"]:
            data["scores"][eid][t["homeAway"]] = {
                "team": t["team"], "score": t["score"],
                "winner": t["winner"], "status": ev.get("status", ""),
                "date": ev.get("date", "")
            }
        captured += 1
    set_cache(data)
    print(f"Captured {captured} new events. Total: {len(data['lineups'])}")
    return captured

# ── ESPN SCORES EN TIEMPO REAL ─────────────────────────────────────────────────
def fetch_espn_scores():
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
            status_type = comp.get("status", {}).get("type", {})
            status = status_type.get("name", "")
            status_detail = status_type.get("shortDetail", status_type.get("detail", ""))
            display_clock = comp.get("status", {}).get("displayClock", "")
            period = comp.get("status", {}).get("period", 0)
            competitors = comp.get("competitors", [])
            if len(competitors) < 2: continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            home_name = es(home.get("team", {}).get("displayName", ""))
            away_name = es(away.get("team", {}).get("displayName", ""))
            home_score = home.get("score", "0")
            away_score = away.get("score", "0")
            def stat_map(c):
                return {s.get("name"): s.get("displayValue", "0") for s in c.get("statistics", [])}
            hs = stat_map(home)
            as_ = stat_map(away)
            scores.append({
                "home": home_name, "away": away_name,
                "homeScore": int(home_score) if str(home_score).isdigit() else 0,
                "awayScore": int(away_score) if str(away_score).isdigit() else 0,
                "status": status, "statusDetail": status_detail,
                "clock": display_clock, "period": period,
                "eventId": ev.get("id", ""),
                "startTime": ev.get("date", ""),
                "homeStats": {
                    "posesion": hs.get("possessionPct", "0"),
                    "tiros": hs.get("totalShots", "0"),
                    "tirosArco": hs.get("shotsOnTarget", "0"),
                    "corners": hs.get("wonCorners", "0"),
                    "faltas": hs.get("foulsCommitted", "0")
                },
                "awayStats": {
                    "posesion": as_.get("possessionPct", "0"),
                    "tiros": as_.get("totalShots", "0"),
                    "tirosArco": as_.get("shotsOnTarget", "0"),
                    "corners": as_.get("wonCorners", "0"),
                    "faltas": as_.get("foulsCommitted", "0")
                }
            })
        return scores
    except Exception as e:
        print(f"Error ESPN scores: {e}")
        return []

# ── MARCA stats ────────────────────────────────────────────────────────────────
def fetch_marca_rank(sort_by):
    try:
        url = f"{MARCA_BASE}/sort/{sort_by}?site=2&mn=50"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get("data", {}).get("rank", [])
    except Exception as e:
        print(f"Error Marca {sort_by}: {e}")
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

# ── SQUADS ────────────────────────────────────────────────────────────────────
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

def fetch_espn_squad(team_name):
    if team_name in _squads_cache:
        return _squads_cache[team_name]
    team_id = ESPN_TEAM_IDS.get(team_name)
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

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats /stored_lineups /squad/<team>"

@app.route("/stats")
def stats():
    scores = fetch_espn_scores()
    data = get_cache()

    # Auto-capturar partidos finalizados no guardados
    for ev in scores:
        if ev.get("status") in ["STATUS_FINAL", "STATUS_FULL_TIME"]:
            eid = ev.get("eventId")
            if eid and not data["lineups"].get(eid):
                edata = fetch_espn_event_full(eid)
                if edata and edata.get("teams_score"):
                    data["lineups"][eid] = edata
                    data["scores"][eid] = {}
                    for t in edata["teams_score"]:
                        data["scores"][eid][t["homeAway"]] = {
                            "team": t["team"], "score": t["score"],
                            "winner": t["winner"], "status": edata.get("status", ""),
                            "date": edata.get("date", "")
                        }
                    set_cache(data)

    # Stats de Marca
    cards_rank  = fetch_marca_rank("cards")
    goals_rank  = fetch_marca_rank("goals")
    assists_rank= fetch_marca_rank("assists")
    saves_rank  = fetch_marca_rank("saves")

    yellow, red, assists, saves, clean = [], [], [], [], []
    for p in cards_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        yc = p.get("cards", 0) - p.get("redCards", 0)
        rc = p.get("redCards", 0)
        if yc > 0: yellow.append({"jugador": name, "seleccion": team, "total": yc})
        if rc > 0: red.append({"jugador": name, "seleccion": team, "total": rc})
    for p in goals_rank:
        pass  # se usa goals_marca abajo
    goals_marca = []
    for p in goals_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        total = p.get("goals", 0)
        if name and total > 0:
            goals_marca.append({"jugador": name, "seleccion": team, "total": total})
    for p in assists_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        total = p.get("assists", 0)
        if name and total > 0:
            assists.append({"jugador": name, "seleccion": team, "total": total})
    for p in saves_rank:
        name = p.get("knownName") or p.get("playerName", "")
        team = es(p.get("teamName", ""))
        sv = p.get("saves", 0)
        gc = p.get("goalsConceded", 0)
        if name and sv > 0:
            saves.append({"jugador": name, "seleccion": team, "total": sv})
        if name and gc == 0 and p.get("games", 0) > 0:
            clean.append({"jugador": name, "seleccion": team, "total": p.get("games", 1)})

    # Stats por equipo desde ESPN (todo el torneo)
    equipos_dict = {}
    try:
        sb = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
            "?dates=20260611-20260719&limit=950",
            timeout=15
        )
        if sb.ok:
            for ev in sb.json().get("events", []):
                for comp in ev.get("competitions", []):
                    st = comp.get("status", {}).get("type", {}).get("name", "")
                    if st not in ["STATUS_IN_PROGRESS","STATUS_HALFTIME","STATUS_FINAL",
                                  "STATUS_FULL_TIME","STATUS_FIRST_HALF","STATUS_SECOND_HALF"]:
                        continue
                    for c in comp.get("competitors", []):
                        team = es(c.get("team", {}).get("displayName", ""))
                        if not team: continue
                        sm = {s.get("name"): s.get("displayValue", "0") for s in c.get("statistics", [])}
                        def num(v):
                            try: return float(v)
                            except: return 0
                        if team not in equipos_dict:
                            equipos_dict[team] = {"seleccion":team,"gf":0,"gc":0,
                                "disparos":0,"tirosArco":0,"corners":0,
                                "faltas":0,"asistencias":0,"posesion":0,"_pj":0}
                        e = equipos_dict[team]
                        e["gf"]         += int(num(sm.get("totalGoals",0)))
                        e["disparos"]   += int(num(sm.get("totalShots",0)))
                        e["tirosArco"]  += int(num(sm.get("shotsOnTarget",0)))
                        e["corners"]    += int(num(sm.get("wonCorners",0)))
                        e["faltas"]     += int(num(sm.get("foulsCommitted",0)))
                        e["asistencias"]+= int(num(sm.get("goalAssists",0)))
                        e["posesion"]   += num(sm.get("possessionPct",0))
                        e["_pj"]        += 1
                    comps = comp.get("competitors", [])
                    if len(comps) == 2:
                        for i, c in enumerate(comps):
                            team = es(c.get("team", {}).get("displayName", ""))
                            rival = comps[1-i]
                            rs = {s.get("name"): s.get("displayValue","0") for s in rival.get("statistics",[])}
                            try: gc = int(float(rs.get("totalGoals",0)))
                            except: gc = 0
                            if team in equipos_dict:
                                equipos_dict[team]["gc"] += gc
    except Exception as e:
        print(f"Error ESPN team stats: {e}")

    equipos = []
    for e in equipos_dict.values():
        pj = e.pop("_pj", 1) or 1
        e["posesion"] = round(e["posesion"] / pj, 1)
        equipos.append(e)
    equipos = sorted(equipos, key=lambda e: (-(e["gf"] or 0), e["gc"] or 0))

    goals_of = fetch_openfootball()
    goals = goals_marca if goals_marca else goals_of

    # Scores: live + stored
    stored_list = []
    for eid, sides in data.get("scores", {}).items():
        home = sides.get("home", {})
        away = sides.get("away", {})
        if home and away and home.get("score","") != "" and away.get("score","") != "":
            stored_list.append({
                "home": home.get("team",""), "away": away.get("team",""),
                "homeScore": home.get("score",""), "awayScore": away.get("score",""),
                "status": home.get("status",""), "eventId": eid
            })
    live_keys = {f"{s['home']}_{s['away']}" for s in scores}
    all_scores = scores + [s for s in stored_list if f"{s['home']}_{s['away']}" not in live_keys]

    result = {
        "goals": goals, "assists": assists, "yellowCards": yellow,
        "redCards": red, "cleanSheets": clean, "saves": saves,
        "equipos": equipos, "scores": all_scores,
        "updated": datetime.utcnow().isoformat() + "Z"
    }
    resp = jsonify(result)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/stored_lineups")
def stored_lineups():
    data = get_cache()
    result = []
    for eid, ev in data.get("lineups", {}).items():
        if ev.get("rosters"):
            result.append({
                "eventId": eid,
                "status": ev.get("status", ""),
                "date": ev.get("date", ""),
                "teams": [
                    {"team": r["team"], "starters": r["starters"], "bench": r["bench"]}
                    for r in ev.get("rosters", [])
                ],
                "boxscore": ev.get("boxscore_teams", []),
            })
    resp = jsonify(result)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/capture_all")
def route_capture_all():
    captured = capture_all_events()
    data = get_cache()
    resp = jsonify({"captured": captured, "total": len(data["lineups"])})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/capture/<event_id>")
def capture_event(event_id):
    data = get_cache()
    ev = fetch_espn_event_full(event_id)
    if not ev:
        return jsonify({"error": "Could not fetch event"}), 500
    data["lineups"][event_id] = ev
    if ev.get("teams_score"):
        data["scores"][event_id] = {}
        for t in ev["teams_score"]:
            data["scores"][event_id][t["homeAway"]] = {
                "team": t["team"], "score": t["score"],
                "winner": t["winner"], "status": ev.get("status",""),
                "date": ev.get("date","")
            }
    set_cache(data)
    resp = jsonify({"ok": True, "event_id": event_id, "status": ev.get("status","")})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/squad/<team_name>")
def squad(team_name):
    result = fetch_espn_squad(team_name)
    if result is None:
        resp = jsonify({"error": "Team not found", "team": team_name})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 404
    resp = jsonify({"team": team_name, "players": result["players"], "coach": result["coach"]})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/stored_scores")
def stored_scores():
    data = get_cache()
    scores_list = []
    for eid, sides in data.get("scores", {}).items():
        home = sides.get("home", {})
        away = sides.get("away", {})
        if home and away:
            scores_list.append({
                "eventId": eid,
                "home": home.get("team",""), "away": away.get("team",""),
                "homeScore": home.get("score",""), "awayScore": away.get("score",""),
                "status": home.get("status",""), "date": home.get("date","")
            })
    resp = jsonify(scores_list)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/debug")
def debug():
    data = get_cache()
    ids = get_all_event_ids()
    resp = jsonify({
        "cached_lineups": len(data.get("lineups",{})),
        "cached_scores": len(data.get("scores",{})),
        "espn_event_ids_found": len(ids),
        "ids": ids[:20]
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/debug_espn_lineup/<event_id>")
def debug_espn_lineup(event_id):
    r = requests.get(
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}",
        timeout=10
    )
    d = r.json()
    rosters = d.get("rosters", [])
    return f"<pre>{json.dumps(rosters, indent=2, ensure_ascii=False)[:5000]}</pre>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
