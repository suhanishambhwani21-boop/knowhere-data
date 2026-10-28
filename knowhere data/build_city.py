import requests, json, time, os, sys

CITY = sys.argv[1] if len(sys.argv) > 1 else "Goa"
CITY_ID = CITY.lower().replace(" ", "-")
HEADERS = {"User-Agent": "knowhere-to-go-data-builder/1.0"}
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

CATEGORIES = {
    "attractions": ['"tourism"~"attraction|museum|viewpoint"', '"historic"', '"leisure"="park"'],
    "hidden-gems": ['"tourism"~"artwork|viewpoint"', '"historic"'],
    "dining": ['"amenity"~"restaurant|cafe|fast_food|food_court"'],
    "stays": ['"tourism"~"hotel|guest_house|hostel|apartment"'],
    "shopping": ['"shop"~"clothes|jewelry|gift|handicraft|antiques|books|art"', '"amenity"="marketplace"'],
    "workshops": ['"craft"', '"amenity"~"studio|arts_centre"'],
    "nightlife": ['"amenity"~"bar|pub|nightclub"'],
}

def get_bbox(city):
    r = requests.get("https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, India", "format": "json", "limit": 1},
        headers=HEADERS, timeout=30)
    r.raise_for_status()
    s, n, w, e = r.json()[0]["boundingbox"]
    return f"{s},{w},{n},{e}"

def run_query(query):
    for attempt in range(4):
        for server in SERVERS:
            try:
                r = requests.post(server, data={"data": query}, headers=HEADERS, timeout=120)
                if r.status_code == 200:
                    return r.json()
            except Exception as ex:
                print("  retrying after error:", ex)
        time.sleep(10)
    return None

def simplify(el):
    t = el.get("tags", {})
    if "name" not in t:
        return None
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lon = el.get("lon") or el.get("center", {}).get("lon")
    if lat is None:
        return None
    keys = ["name", "cuisine", "opening_hours", "website", "phone", "image",
            "wikimedia_commons", "wikidata", "addr:street", "addr:suburb",
            "diet:vegetarian", "charge", "fee", "stars"]
    p = {k: t[k] for k in keys if k in t}
    p["id"] = f'{el["type"][0]}{el["id"]}'
    p["lat"], p["lng"] = round(lat, 5), round(lon, 5)
    return p

os.makedirs("data", exist_ok=True)
bbox = get_bbox(CITY)
print("City:", CITY, "bbox:", bbox)

for cat, filters in CATEGORIES.items():
    parts = "".join(f"nwr[{f}]({bbox});" for f in filters)
    query = f"[out:json][timeout:90];({parts});out center tags 1000;"
    print("Fetching", cat, "...")
    data = run_query(query)
    if data is None:
        print("  FAILED:", cat)
        continue
    seen, places = set(), []
    for el in data["elements"]:
        p = simplify(el)
        if p and (p["name"].lower(), round(p["lat"], 3), round(p["lng"], 3)) not in seen:
            seen.add((p["name"].lower(), round(p["lat"], 3), round(p["lng"], 3)))
            places.append(p)
    with open(f"data/{CITY_ID}-{cat}.json", "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False)
    print("  saved", len(places), "places")
    time.sleep(8)

print("Done. Files are in the 'data' folder.")