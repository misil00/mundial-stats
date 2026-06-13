from flask import Flask, jsonify
import requests
from datetime import datetime
from bs4 import BeautifulSoup

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
    "Ivory Coast":"Costa de Marfil","Paraguay":"Paraguay","Qatar":"Qatar",
    "Curaçao":"Curazao","Côte d'Ivoire":"Costa de Marfil"
}

def es(name):
    return NAME_MAP.get(name, name)

def scrape(url):
    """Fetch any URL via ScraperAPI - bypasses all blocks"""
    try:
        r = requests.get(SCRAPER_URL, params={"api_key": SCRAPER_KEY, "url": url}, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"ScraperAPI error for {url}: {e}")
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
        goals = sorted(scorers.values(), key=lambda x: -x["total"])[:15]
        return goals, scores
    except Exception as e:
        print(f"Error openfootball: {e}")
        return [], []

def parse_marca_table(url, col_map):
    """Parse a Marca stats table. col_map = {col_index: field_name}"""
    html = scrape(url)
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        # Buscar tabla de estadísticas
        table = soup.find("table")
        if not table:
            # Buscar por clase
            table = soup.find("div", class_=lambda x: x and "table" in x.lower())
        if not table:
            print(f"No table found in {url}")
            return []
        rows = table.find_all("tr")[1:]  # Skip header
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            jugador = texts[1] if len(texts) > 1 else ""
            seleccion = texts[2] if len(texts) > 2 else ""
            if not jugador or jugador.isdigit():
                continue
            total = 0
            for idx, field in col_map.items():
                if idx < len(texts):
                    try:
                        total = int(texts[idx])
                        break
                    except:
                        pass
            if jugador and seleccion and total > 0:
                results.append({
                    "jugador": jugador,
                    "seleccion": es(seleccion),
                    "total": total
                })
        return results[:15]
    except Exception as e:
        print(f"Parse error {url}: {e}")
        return []

@app.route("/stats")
def stats():
    goals, scores = fetch_openfootball()

    # Scraping Marca via ScraperAPI
    yellow = parse_marca_table("https://us.marca.com/soccer/mundial/tarjetas.html", {3: "ta"})
    red_raw = parse_marca_table("https://us.marca.com/soccer/mundial/tarjetas.html", {4: "tr"})
    assists = parse_marca_table("https://us.marca.com/soccer/mundial/asistencias.html", {3: "ast"})
    saves = parse_marca_table("https://us.marca.com/soccer/mundial/porteros.html", {3: "saves"})

    result = {
        "goals": goals,
        "assists": assists,
        "yellowCards": yellow,
        "redCards": red_raw,
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
    html = scrape("https://us.marca.com/soccer/mundial/tarjetas.html")
    if not html:
        return "ScraperAPI failed"
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    return f"Tables found: {len(tables)} | HTML length: {len(html)} | Preview: {html[:500]}"

@app.route("/")
def index():
    return "Mundial 2026 Stats API OK - /stats /debug"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
