#!/usr/bin/env python3
"""OpenStreetMap çevresi → kaynak/osm.json (metre; x doğu, y kuzey; orijin balkon 3B ile aynı).

Ham .osm: araclar/site-3b/kaynak/osm-cevre.osm; yoksa api.openstreetmap.org'dan indirilir (site ± ~450 m).
Yalnız sahnede kullanılanlar tutulur: binalar, yollar, alan kullanımı (çim, orman, park, saha, oyun alanı), ağaç düğümleri.
© OpenStreetMap katkıcıları, ODbL.

    python3 araclar/site-3b/kaynak-hazirla.py
"""
import json, math, os, urllib.request
import xml.etree.ElementTree as ET
KOK = os.path.dirname(os.path.abspath(__file__))
HAM = f"{KOK}/kaynak/osm-cevre.osm"
KUTU = "28.9370,41.0858,28.9490,41.0938"
O = (41.090056, 28.943083)                          # balkon/rapor/cephe-3d/osm-izler.json ile aynı orijin
K = 111320.0; KX = K * math.cos(math.radians(O[0]))
if not os.path.exists(HAM):
    eski = f"{KOK}/../../balkon/rapor/cephe-3d/osm-cevre.osm"
    if os.path.exists(eski): HAM = eski
    else:
        ist = urllib.request.Request(f"https://api.openstreetmap.org/api/0.6/map?bbox={KUTU}", headers={"User-Agent": "5levent-site-3b/1.0"})
        open(HAM, "wb").write(urllib.request.urlopen(ist, timeout=90).read())
kok = ET.parse(HAM).getroot()
nd = {n.get("id"): (round((float(n.get("lon")) - O[1]) * KX, 2), round((float(n.get("lat")) - O[0]) * K, 2)) for n in kok.iter("node")}
TUT = ("building", "highway", "landuse", "leisure", "natural", "amenity", "barrier", "name", "building:levels", "height", "service",
       "oneway", "lanes", "sport", "surface", "area", "layer", "bridge", "tunnel", "level", "residential")
yollar, binalar, alanlar, agac = [], [], [], []
for w in kok.iter("way"):
    t = {x.get("k"): x.get("v") for x in w.iter("tag")}
    p = [nd[x.get("ref")] for x in w.iter("nd") if x.get("ref") in nd]
    if len(p) < 2: continue
    t = {k: v for k, v in t.items() if k in TUT}
    kayit = {"id": int(w.get("id")), "t": t, "p": p}
    if "building" in t: binalar.append(kayit)
    elif t.get("highway") and t.get("highway") not in ("proposed", "construction") and t.get("area") != "yes": yollar.append(kayit)
    elif any(k in t for k in ("landuse", "leisure", "natural", "amenity")) or t.get("area") == "yes": alanlar.append(kayit)
for n in kok.iter("node"):
    t = {x.get("k"): x.get("v") for x in n.iter("tag")}
    if t.get("natural") == "tree": agac.append(nd[n.get("id")])
json.dump({"kaynak": "© OpenStreetMap katkıcıları (ODbL), api.openstreetmap.org/api/0.6/map", "orijin": {"enlem": O[0], "boylam": O[1]},
           "birim": "metre; x doğu, y kuzey", "binalar": binalar, "yollar": yollar, "alanlar": alanlar, "agac": agac},
          open(f"{KOK}/kaynak/osm.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"bina {len(binalar)} · yol {len(yollar)} · alan {len(alanlar)} · ağaç {len(agac)} → kaynak/osm.json",
      round(os.path.getsize(f"{KOK}/kaynak/osm.json") / 1024), "KB")
