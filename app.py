from flask import Flask, jsonify, request
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

SCRAPER_KEY = "95382bf00c8f549468a92828c1428f3f"
SCRAPER_URL = "https://api.scraperapi.com"
OF_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

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
    "Ivory Coast":"Costa de Marfil","Paraguay":"Paraguay","Qatar":"Qatar"
}

def es(name):
    return NAME_MAP.get(name, name)

def scrape(url):
    try:
        r = requests.get(SCRAPER_URL, params={"api_key": SCRAPER_KEY, "url": url, "render": "true"}, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"ScraperAPI error: {e}")
        return None

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

def parse_marca(url):
    html = scrape(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    
    # Buscar todas las filas con datos de jugadores
    # Marca usa diferentes estructuras - buscar por texto
    rows = soup.find_all("tr")
    print(f"Filas encontradas en {url}: {len(rows)}")
    
    for row in rows:
        cells = row.find_all(["td","th"])
        if len(cells) < 3:
            continue
        texts = [c.get_text(separator=" ", strip=True) for c in cells]
        
        # Skip headers
        if any(t.lower() in ["jugador","equipo","player","team","pos"] for t in texts[:3]):
            continue
            
        # Buscar nombre y equipo
        jugador = ""
        seleccion = ""
        total = 0
        
        for i, t in enumerate(texts):
            if t and not t.isdigit() and len(t) > 2 and not jugador:
                if not any(c.isdigit() for c in t) or len(t) > 10:
                    jugador = t
            elif jugador and not t.isdigit() and len(t) > 2 and not seleccion:
                seleccion = t
            elif t.isdigit() and jugador and seleccion and not total:
                total = int(t)
        
        if jugador and seleccion and total > 0:
            results.append({"jugador": jugador, "seleccion": es(seleccion), "total": total})
    
    return results[:15]

@app.route("/stats")
def stats():
    goals, scores = fetch_openfootball()
    yellow = parse_marca("https://us.marca.com/soccer/mundial/tarjetas.html")
    assists = parse_marca("https://us.marca.com/soccer/mundial/asistencias.html")

    result = {
        "goals": goals,
        "assists": assists,
        "yellowCards": yellow,
        "redCards": [],
        "cleanSheets": [],
        "saves": [],
        "scores": scores,
        "updated": datetime.utcnow().isoformat() + "Z"
    }
    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/debug")
def debug():
    url = request.args.get("url", "https://us.marca.com/soccer/mundial/tarjetas.html")
    html = scrape(url)
    if not html:
        return "ScraperAPI failed"
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    rows = soup.find_all("tr")
    # Mostrar primeras filas con contenido
    sample = []
    for row in rows[:20]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
        if cells:
            sample.append(str(cells))
    return f"Tables: {len(tables)} | Rows: {len(rows)} | HTML: {len(html)}<br><br>" + "<br>".join(sample)

@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats /debug"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
