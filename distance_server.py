"""
Local sailing distance lookup service.
Uses searoute (free, offline) to calculate actual sea route distances.
Uses GeoNames API to resolve port codes to coordinates.

Usage:
  python distance_server.py [geonames_username]

Then the service runs on http://localhost:8898

API:
  GET /distance?from=CNSHA&to=SGSIN
  GET /distance?from=CNSHA&to=SGSIN&geonames_user=xxx
  GET /health

Returns:
  {"from": "CNSHA", "to": "SGSIN", "distance_nm": 2215, "method": "searoute"}
"""

import sys
import os
import json
import requests as http_requests
import searoute
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# GeoNames cache: port_code -> (lat, lon)
GEO_CACHE = {}

# All port coordinates from ports.csv (code -> [lat, lon])
# Covers 244 ports - no external API needed for known ports
COMMON_PORTS = {
    "AEAUH": [24.47, 54.37],
    "AEDUB": [25.25, 55.28],
    "AEDXB": [25.25, 55.28],
    "AEFJR": [25.12, 56.33],
    "AEJEA": [25.02, 55.03],
    "AEKLF": [25.53, 56.35],
    "AUBNE": [-27.38, 153.13],
    "AUDAM": [-32.07, 115.75],
    "AUPHE": [-31.94, 115.87],
    "AUSYD": [-33.95, 151.18],
    "BDCGP": [22.27, 91.80],
    "BDDAC": [23.73, 90.39],
    "BEANR": [51.23, 4.42],
    "BEZEE": [51.33, 3.21],
    "BRSSZ": [-23.97, -46.30],
    "CNAJG": [30.95, 120.00],
    "CNAQG": [30.53, 117.05],
    "CNBIH": [21.49, 109.12],
    "CNBJS": [39.92, 116.40],
    "CNCDU": [30.57, 104.07],
    "CNCGC": [43.88, 125.32],
    "CNCGU": [31.65, 120.74],
    "CNCOZ": [23.66, 116.62],
    "CNCQI": [29.56, 106.55],
    "CNCSH": [28.23, 112.94],
    "CNCWN": [22.59, 113.84],
    "CNDAL": [38.91, 121.60],
    "CNDCB": [22.53, 113.87],
    "CNDGG": [23.04, 113.75],
    "CNFAN": [21.62, 108.35],
    "CNFOS": [23.02, 113.12],
    "CNFZH": [26.07, 119.40],
    "CNGGZ": [23.10, 113.32],
    "CNGYA": [26.65, 106.63],
    "CNHAZ": [30.27, 120.15],
    "CNHEY": [23.73, 114.69],
    "CNHFI": [31.86, 117.28],
    "CNHHH": [40.84, 111.75],
    "CNHKG": [22.30, 114.17],
    "CNHKO": [20.04, 110.35],
    "CNHMN": [22.92, 113.41],
    "CNHRN": [45.75, 126.65],
    "CNHSC": [24.80, 113.60],
    "CNHSI": [30.23, 115.04],
    "CNHUA": [23.11, 113.36],
    "CNHUI": [23.08, 114.41],
    "CNJAS": [30.75, 121.18],
    "CNJGY": [31.91, 120.28],
    "CNJIU": [29.73, 116.00],
    "CNJMN": [22.59, 113.08],
    "CNJNA": [36.65, 116.98],
    "CNJYG": [23.55, 116.37],
    "CNKNM": [25.04, 102.73],
    "CNLAZ": [36.06, 103.83],
    "CNLHA": [29.65, 91.14],
    "CNLYG": [34.60, 119.22],
    "CNMEZ": [24.31, 116.12],
    "CNMMI": [21.66, 110.92],
    "CNNAS": [22.75, 113.58],
    "CNNCH": [28.68, 115.89],
    "CNNGB": [29.87, 121.55],
    "CNNIN": [22.82, 108.37],
    "CNNJG": [32.06, 118.78],
    "CNNSA": [22.53, 114.10],
    "CNNTG": [31.98, 120.88],
    "CNOCT": [38.93, 117.72],
    "CNQGY": [23.68, 113.06],
    "CNQIN": [21.49, 108.35],
    "CNQZH": [21.97, 108.62],
    "CNQZL": [24.87, 118.59],
    "CNQZW": [24.78, 118.52],
    "CNRZH": [35.42, 119.46],
    "CNSHA": [31.23, 121.47],
    "CNSHK": [22.48, 113.92],
    "CNSHY": [41.80, 123.43],
    "CNSJZ": [38.04, 114.51],
    "CNSNZ": [22.55, 114.10],
    "CNSWA": [23.35, 116.68],
    "CNSWE": [22.79, 115.38],
    "CNTAC": [31.45, 121.14],
    "CNTAO": [36.07, 120.38],
    "CNTNJ": [38.98, 117.72],
    "CNTOL": [30.95, 117.81],
    "CNTYU": [37.87, 112.55],
    "CNURM": [43.82, 87.62],
    "CNWHA": [30.59, 114.31],
    "CNWNZ": [27.99, 120.70],
    "CNWUH": [31.33, 118.38],
    "CNXGG": [39.02, 117.72],
    "CNXIA": [34.26, 108.94],
    "CNXMN": [24.45, 118.08],
    "CNXNT": [36.62, 101.77],
    "CNYCH": [38.47, 106.27],
    "CNYIB": [28.77, 104.63],
    "CNYIC": [30.69, 111.29],
    "CNYJI": [21.86, 111.98],
    "CNYPN": [19.70, 110.70],
    "CNYTN": [22.60, 114.27],
    "CNYUF": [22.92, 112.04],
    "CNZEJ": [32.19, 119.45],
    "CNZGZ": [34.75, 113.65],
    "CNZJG": [29.95, 122.10],
    "CNZNG": [21.19, 110.36],
    "CNZOS": [29.95, 122.10],
    "CNZPU": [30.60, 121.14],
    "CNZQG": [23.04, 112.46],
    "CNZSN": [22.52, 113.38],
    "CNZUH": [22.27, 113.58],
    "DEHAM": [53.55, 9.99],
    "DJJIB": [11.60, 43.15],
    "EGALY": [31.20, 29.92],
    "EGDAM": [31.42, 32.35],
    "EGPSD": [31.27, 32.34],
    "EGSOK": [29.94, 32.52],
    "EGSUZ": [30.00, 32.55],
    "ETADD": [9.02, 38.75],
    "FRLEH": [47.21, -1.58],
    "GBIMM": [53.58, -0.24],
    "GBLIV": [53.41, -2.99],
    "GBLON": [51.51, -0.13],
    "GBSOU": [50.90, -1.40],
    "GBTIL": [51.46, 0.35],
    "GEPTI": [42.15, 41.72],
    "GRPIR": [37.94, 23.64],
    "HKHKG": [22.30, 114.17],
    "IDBLW": [3.78, 98.68],
    "IDJKT": [-6.10, 106.85],
    "IDSRG": [-6.97, 110.42],
    "IDSUB": [-7.25, 112.74],
    "ILASD": [31.80, 34.65],
    "ILHFA": [32.82, 34.99],
    "INAMD": [23.03, 72.58],
    "INBGJ": [27.01, 84.15],
    "INBOM": [18.95, 72.84],
    "INCCU": [22.57, 88.36],
    "INCOK": [9.97, 76.30],
    "INDAD": [28.57, 77.33],
    "INDDL": [30.91, 75.85],
    "INDER": [28.57, 77.33],
    "INFBD": [28.41, 77.32],
    "INHAR": [28.45, 76.95],
    "INHYD": [17.39, 78.49],
    "INICD": [28.63, 77.22],
    "INJAI": [26.92, 75.79],
    "INJDP": [26.24, 73.02],
    "INKAT": [13.28, 80.35],
    "INKHO": [23.03, 72.58],
    "INLDH": [30.90, 75.85],
    "INLON": [28.68, 77.33],
    "INLUD": [30.90, 75.85],
    "INMAA": [13.10, 80.30],
    "INMUN": [22.47, 69.71],
    "INNAG": [21.15, 79.08],
    "INNSA": [18.95, 72.95],
    "INPAT": [28.62, 77.27],
    "INPAV": [21.49, 72.19],
    "INPPG": [28.62, 77.29],
    "INPUN": [18.52, 73.86],
    "INPWL": [28.28, 77.37],
    "INQRP": [30.85, 75.88],
    "INSON": [28.68, 77.01],
    "INSSA": [23.03, 72.58],
    "INSWA": [30.85, 75.88],
    "INTKD": [28.50, 77.25],
    "INTUB": [28.38, 77.12],
    "INVIZ": [17.69, 83.29],
    "IQEBL": [36.19, 44.02],
    "IQSYH": [35.56, 45.43],
    "IQZAO": [37.14, 42.68],
    "JOAMM": [31.95, 35.93],
    "JOAQJ": [29.53, 35.06],
    "JPNGO": [34.18, 133.00],
    "JPOSA": [34.67, 135.23],
    "JPTYO": [35.43, 139.65],
    "JPUKB": [34.68, 135.18],
    "JPYOK": [35.44, 139.64],
    "KEMBA": [-4.06, 39.67],
    "KHKOS": [10.61, 103.53],
    "KHPNH": [11.56, 104.92],
    "KRINC": [37.45, 126.40],
    "KRKAN": [34.98, 127.53],
    "KRPUS": [35.10, 129.04],
    "KRSEL": [37.56, 127.00],
    "KRUSN": [35.58, 129.32],
    "LAVTE": [17.97, 102.63],
    "LBBEY": [33.90, 35.51],
    "LKCMB": [6.93, 79.85],
    "LRMLW": [6.31, -10.80],
    "LYBEN": [32.12, 20.07],
    "LYKHO": [32.65, 14.26],
    "LYMRA": [32.38, 15.09],
    "MHMAJ": [7.10, 171.38],
    "MMNPD": [19.76, 96.07],
    "MMRGN": [16.87, 96.20],
    "MOMFM": [22.20, 113.55],
    "MYKCH": [1.55, 110.35],
    "MYKUL": [3.14, 101.69],
    "MYPEN": [5.42, 100.34],
    "MYPGU": [1.44, 103.79],
    "MYPKG": [3.00, 101.40],
    "MYPKN": [3.00, 101.40],
    "MYPTP": [1.44, 103.79],
    "MYTPP": [1.46, 103.60],
    "NLAMS": [52.37, 4.90],
    "NLRTM": [51.92, 4.50],
    "OMMCT": [23.62, 58.59],
    "OMSLL": [17.02, 54.09],
    "OMSOH": [24.35, 56.73],
    "PBBQM": [24.78, 67.35],
    "PHMNL": [14.58, 120.97],
    "PHMNN": [14.62, 120.97],
    "PHSPS": [14.78, 120.28],
    "PKISB": [33.69, 73.04],
    "PKKHI": [24.85, 66.98],
    "PLWAW": [52.23, 21.01],
    "PTSIN": [38.72, -9.14],
    "QAHMD": [25.50, 51.85],
    "ROCND": [44.22, 28.64],
    "SADAB": [21.47, 39.19],
    "SADMM": [26.07, 50.18],
    "SAJED": [24.17, 38.06],
    "SANEO": [24.28, 38.50],
    "SARUH": [24.71, 46.68],
    "SDPZU": [20.00, 37.22],
    "SGSIN": [1.27, 103.85],
    "SOBBO": [10.44, 45.02],
    "SYDAM": [33.51, 36.29],
    "SYLTR": [35.52, 35.79],
    "THBKK": [13.68, 100.50],
    "THBKS": [13.72, 100.51],
    "THLCH": [7.88, 98.39],
    "THLKB": [13.75, 100.73],
    "THSCS": [13.67, 100.51],
    "TRALI": [38.80, 26.94],
    "TRIST": [41.27, 29.74],
    "TRIZT": [40.78, 29.75],
    "TRMAR": [40.91, 29.12],
    "TRMER": [36.81, 34.64],
    "TWHSC": [24.80, 120.98],
    "TWHSZ": [24.80, 120.96],
    "TWKEL": [25.13, 121.74],
    "TWKHH": [22.60, 120.30],
    "TWNTC": [25.01, 121.46],
    "TWTPE": [25.05, 121.47],
    "TWTXG": [24.15, 120.65],
    "TWTYN": [25.01, 121.30],
    "UAODS": [46.49, 30.74],
    "USLAX": [33.74, -118.27],
    "USLGB": [33.75, -118.20],
    "USOAK": [37.80, -122.27],
    "USSEA": [47.54, -122.33],
    "VNCAT": [11.00, 109.23],
    "VNDAD": [16.07, 108.22],
    "VNHAN": [21.03, 105.85],
    "VNHPH": [20.85, 106.68],
    "VNHPP": [10.75, 106.70],
    "VNSGN": [10.76, 106.66],
    "VNVUT": [10.82, 106.64],
    "YEADE": [12.80, 45.03],
    "YEHOD": [14.80, 42.95],
}


def try_geonames(username, query, country=None, feature_class=None):
    """Try a single GeoNames search. Returns (lat, lon) or None."""
    params = {
        "q": query,
        "maxRows": 5,
        "username": username,
    }
    if country:
        params["country"] = country
    if feature_class:
        params["featureClass"] = feature_class
    resp = http_requests.get(
        "https://secure.geonames.org/searchJSON",
        params=params,
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        results = data.get("geonames", [])
        if results:
            hit = results[0]
            return (float(hit["lat"]), float(hit["lng"]))
    return None


def try_nominatim(query):
    """Try Nominatim (OpenStreetMap) search. Free, no API key needed."""
    try:
        resp = http_requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "ShippingSchedule/1.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception as e:
        print(f"Nominatim lookup failed for '{query}': {e}", file=sys.stderr)
    return None


def lookup_coords(port_code, geonames_user, port_name=None):
    """Resolve a port code to (lat, lon) coordinates."""
    if port_code in GEO_CACHE:
        return GEO_CACHE[port_code]

    # Try common ports first
    if port_code in COMMON_PORTS:
        lat, lon = COMMON_PORTS[port_code]
        GEO_CACHE[port_code] = (lat, lon)
        return (lat, lon)

    country = port_code[:2]
    loc_name = port_code[2:]

    # Try GeoNames API (multiple strategies)
    if geonames_user:
        try:
            for args in [
                (geonames_user, loc_name, country, "H"),
                (geonames_user, loc_name, country, None),
                (geonames_user, loc_name + " port", country, None),
                (geonames_user, loc_name, None, None),
            ]:
                result = try_geonames(*args)
                if result:
                    GEO_CACHE[port_code] = result
                    return result

            # Also try with port_name from ports.csv
            if port_name:
                clean_name = port_name.split("/")[0].strip().strip(",")
                result = try_geonames(geonames_user, clean_name, country)
                if result:
                    GEO_CACHE[port_code] = result
                    return result
        except Exception as e:
            print(f"GeoNames lookup failed for {port_code}: {e}", file=sys.stderr)

    # Fallback: Nominatim (free, no key needed)
    # Build queries in priority order
    nom_queries = []
    if port_name:
        clean = port_name.split("/")[0].split(",")[0].strip()
        if clean:
            nom_queries.append(f"{clean} port {country}")
            nom_queries.append(clean)
    nom_queries.append(f"{loc_name} port {country}")
    nom_queries.append(f"{loc_name} {country}")

    for q in nom_queries:
        result = try_nominatim(q)
        if result:
            GEO_CACHE[port_code] = result
            return result

    return None


def calc_sailing_distance(coord1, coord2):
    """Calculate sailing distance using searoute."""
    lon1, lat1 = coord1[1], coord1[0]  # searoute takes (lon, lat)
    lon2, lat2 = coord2[1], coord2[0]
    try:
        route = searoute.searoute((lon1, lat1), (lon2, lat2), units="naut")
        return round(route["properties"]["length"])
    except Exception as e:
        print(f"Searoute calculation failed: {e}", file=sys.stderr)
        return None


@app.route("/distance")
def distance():
    from_code = request.args.get("from", "").upper().strip()
    to_code = request.args.get("to", "").upper().strip()
    from_name = request.args.get("from_name", "").strip() or None
    to_name = request.args.get("to_name", "").strip() or None
    geonames_user = request.args.get("geonames_user", "").strip()

    if not from_code or not to_code:
        return jsonify({"error": "Missing 'from' or 'to' parameter"}), 400

    if from_code == to_code:
        return jsonify({"from": from_code, "to": to_code, "distance_nm": 0, "method": "same_port"})

    # Lookup coordinates (pass port names for GeoNames fallback)
    c1 = lookup_coords(from_code, geonames_user, from_name)
    c2 = lookup_coords(to_code, geonames_user, to_name)

    if not c1:
        return jsonify({"error": f"Cannot find coordinates for port: {from_code}", "port": from_code}), 404
    if not c2:
        return jsonify({"error": f"Cannot find coordinates for port: {to_code}", "port": to_code}), 404

    # Calculate sailing distance
    dist = calc_sailing_distance(c1, c2)
    if dist is None:
        return jsonify({"error": "Sailing distance calculation failed"}), 500

    return jsonify({
        "from": from_code,
        "to": to_code,
        "distance_nm": dist,
        "method": "searoute",
        "coords": {
            "from": {"lat": c1[0], "lon": c1[1]},
            "to": {"lat": c2[0], "lon": c2[1]}
        }
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "cached_ports": len(GEO_CACHE)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8898))
    print(f"Sailing distance service starting on http://0.0.0.0:{port}")
    print("API: GET /distance?from=CNSHA&to=SGSIN")
    print("      GET /distance?from=CNSHA&to=SGSIN&geonames_user=xxx")
    print("      GET /health")
    app.run(host="0.0.0.0", port=port, debug=False)
