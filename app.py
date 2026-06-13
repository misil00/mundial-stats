from flask import Flask, jsonify
import requests
from datetime import datetime
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "es-US,es;q=0.9"
}

OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

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
    "Curaçao":"Curazao","Côte d'Ivoire":"Costa de Marfil",
    "Costa Rica":"Costa Rica","Honduras":"Honduras","El Salvador":"El Salvador"
}

def es(name):
    return NAME_MAP.get(name, name)

def fetch_openfootball():
    """Goles y scores desde openfootball"""
    try:
        r = requests.get(OPENFOOTBALL_URL, headers=HEADERS, timeout=15)
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
        goals = sorted(scorers.values(), key=lambda x: -x["total"])[:15]
        return goals, scores
    except Exception as e:
        print(f"Error openfootball: {e}")
        return [], []

def fetch_marca_stats(stat_type):
    """Scraping de Marca para tarjetas, asistencias, paradas"""
    urls = {
        "tarjetas": "https://us.marca.com/soccer/mundial/tarjetas.html",
        "asistencias": "https://us.marca.com/soccer/mundial/asistencias.html",
        "paradas": "https://us.marca.com/soccer/mundial/porteros.html",
    }
    url = urls.get(stat_type)
    if not url:
        return []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text
        
        # Buscar tabla de estadísticas en el HTML
        players = []
        
        # Buscar filas de datos - patrón de Marca
        # Buscar por clase de fila o por estructura de tabla
        rows = re.findall(r'<tr[^>]*class="[^"]*stat[^"]*"[^>]*>(.*?)</tr>', html, re.DOTALL)
        if not rows:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        
        for row in rows:
            # Extraer celdas
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            cells = [c for c in cells if c]
            
            if len(cells) >= 3:
                # Estructura típica: pos, jugador, equipo, stats...
                jugador = cells[1] if len(cells) > 1 else cells[0]
                seleccion = cells[2] if len(cells) > 2 else ""
                
                # Limpiar nombres
                jugador = re.sub(r'\s+', ' ', jugador).strip()
                seleccion = re.sub(r'\s+', ' ', seleccion).strip()
                
                if not jugador or jugador.isdigit() or len(jugador) < 2:
                    continue
                
                # Total según tipo
                total = 0
                if stat_type == "tarjetas" and len(cells) > 3:
                    try: total = int(cells[3])
                    except: total = 1
                elif stat_type == "asistencias" and len(cells) > 3:
                    try: total = int(cells[3])
                    except: total = 1
                elif stat_type == "paradas" and len(cells) > 3:
                    try: total = int(cells[3])
                    except: total = 1
                else:
                    total = 1
                    
                if jugador and seleccion:
                    players.append({
                        "jugador": jugador,
                        "seleccion": es(seleccion),
                        "total": total
                    })
        
        return players[:15]
    except Exception as e:
        print(f"Error Marca {stat_type}: {e}")
        return []

def fetch_marca_cards():
    """Tarjetas amarillas y rojas desde Marca"""
    try:
        r = requests.get("https://us.marca.com/soccer/mundial/tarjetas.html", headers=HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text
        
        yellow = []
        red = []
        
        # Buscar filas con datos de jugadores
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            cells = [c for c in cells if c and not c.isspace()]
            
            if len(cells) < 4:
                continue
            
            # Buscar nombre de jugador (segunda celda normalmente)
            jugador = ""
            seleccion = ""
            ta = 0
            tr = 0
            
            for i, c in enumerate(cells):
                if c.isdigit():
                    continue
                if len(c) > 2 and not c.isdigit() and i == 1:
                    jugador = c
                elif len(c) > 2 and not c.isdigit() and i == 2:
                    seleccion = c
            
            # Buscar números para TA y TR
            nums = [c for c in cells if c.isdigit()]
            if len(nums) >= 2:
                try: ta = int(nums[0])
                except: pass
                try: tr = int(nums[1])
                except: pass
            elif len(nums) == 1:
                try: ta = int(nums[0])
                except: pass
            
            if jugador and seleccion:
                if ta > 0:
                    yellow.append({"jugador": jugador, "seleccion": es(seleccion), "total": ta})
                if tr > 0:
                    red.append({"jugador": jugador, "seleccion": es(seleccion), "total": tr})
        
        return yellow, red
    except Exception as e:
        print(f"Error Marca cards: {e}")
        return [], []

@app.route("/stats")
def stats():
    goals, scores = fetch_openfootball()
    yellow, red = fetch_marca_cards()
    assists = fetch_marca_stats("asistencias")
    saves = fetch_marca_stats("paradas")

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

@app.route("/")
def index():
    return "Mundial 2026 Stats API OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
