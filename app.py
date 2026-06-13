from flask import Flask, jsonify
import requests
from datetime import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)

SCRAPER_KEY = "95382bf00c8f549468a92828c1428f3f"
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
        r = requests.get(
            "https://api.scraperapi.com",
            params={"api_key": SCRAPER_KEY, "url": url, "render": "true"},
            timeout=30
        )
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"ScraperAPI error {url}: {e}")
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

def parse_fichajes(stat):
    """Scraping fichajes.com para tarjetas amarillas/rojas/asistencias"""
    urls = {
        "yellowCards": "https://www.fichajes.com/mundo/copa-mundial/estadistica-jugadores/tarjetas-amarillas",
        "redCards": "https://www.fichajes.com/mundo/copa-mundial/estadistica-jugadores/tarjetas-rojas",
        "assists": "https://www.fichajes.com/mundo/copa-mundial/estadistica-jugadores/asistencias",
    }
    url = urls.get(stat)
    if not url:
        return []
    html = scrape(url)
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        # fichajes.com usa tabla con clase específica
        rows = soup.select("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            # Buscar nombre de jugador y selección
            jugador = ""
            seleccion = ""
            total = 0
            for i, t in enumerate(texts):
                if not t or t.isdigit():
                    continue
                if len(t) > 2 and not jugador and not any(c.isdigit() for c in t):
                    jugador = t
                elif jugador and len(t) > 2 and not seleccion and not any(c.isdigit() for c in t):
                    seleccion = t
            nums = [t for t in texts if t.isdigit()]
            if nums:
                total = int(nums[0])
            if jugador and seleccion and total > 0:
                results.append({"jugador": jugador, "seleccion": es(seleccion), "total": total})
        return results[:15]
    except Exception as e:
        print(f"Parse error {stat}: {e}")
        return []

@app.route("/stats")
def stats():
    goals, scores = fetch_openfootball()
    yellow = parse_fichajes("yellowCards")
    red = parse_fichajes("redCards")
    assists = parse_fichajes("assists")

    result = {
        "goals": goals,
        "assists": assists,
        "yellowCards": yellow,
        "redCards": red,
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
    url = "https://www.fichajes.com/mundo/copa-mundial/estadistica-jugadores/tarjetas-amarillas"
    html = scrape(url)
    if not html:
        return "ScraperAPI failed"
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr")
    sample = []
    for row in rows[:15]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
        if cells:
            sample.append(str(cells))
    return f"Rows: {len(rows)} | HTML: {len(html)}<br><br>" + "<br>".join(sample)

@app.route("/")
def index():
    return "Mundial 2026 Stats API - /stats /debug"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
