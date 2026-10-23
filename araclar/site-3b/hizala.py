"""Pafta pikseli → site metresi dönüşümleri (benzerlik: döndür + ölçekle + kaydır).

- Blok kat planı (Ek-6/Ek-8) → OSM bina izi: plan dış hattı ile OSM izinin örtüşmesi (IoU) en büyük olacak biçimde
  açı, ölçek ve konum aranır. Açı ön bilgisi balkon/rapor/cephe-3d/konum.py'den: plan "üst"ü kuzey (≈10° batıya),
  B3'te batı. Ölçek Ek-6 cm ölçü etiketlerinden (A için aranır).
- Vaziyet planı (Ek-5 s.35) → site: aynı paftadaki blok merkezleri ↔ OSM merkezleri, en küçük kareler (cevre-uret.py ile aynı yöntem).
"""
import json, math, os
import numpy as np, cv2
KOK = os.path.dirname(os.path.abspath(__file__))

def don(T, pts):
    """T = (aci, olcek, cx, cy, tx, ty): pafta (x sağ, y aşağı) → site (x doğu, y kuzey)."""
    a, s, cx, cy, tx, ty = T; c, si = math.cos(a), math.sin(a)
    return [[round((x - cx) * s * c - (-(y - cy)) * s * si + tx, 2), round((x - cx) * s * si + (-(y - cy)) * s * c + ty, 2)] for x, y in pts]

def _maske(polys, x0, y0, r, w, h):
    m = np.zeros((h, w), np.uint8)
    for p in polys: cv2.fillPoly(m, [np.array([[(x - x0) / r, (y0 - y) / r] for x, y in p], np.int32)], 1)
    return m

def iou(a, b, r=.2):
    xs = [x for x, y in a + b]; ys = [y for x, y in a + b]
    x0, y0 = min(xs) - 2, max(ys) + 2; w, h = int((max(xs) - x0 + 2) / r), int((y0 - min(ys) + 2) / r)
    A, B = _maske([a], x0, y0, r, w, h), _maske([b], x0, y0, r, w, h)
    return (A & B).sum() / max(1, (A | B).sum())

def blok_hizala(dis_px, osm, aci0, olcek0, olcek_ara=False):
    cx = sum(x for x, y in dis_px) / len(dis_px); cy = sum(y for x, y in dis_px) / len(dis_px)
    ox = sum(x for x, y in osm) / len(osm); oy = sum(y for x, y in osm) / len(osm)
    en = (-1, None)
    olcekler = np.linspace(olcek0 * .9, olcek0 * 1.1, 11) if olcek_ara else [olcek0]
    for s in olcekler:                                   # kaba arama
        for da in np.radians(np.arange(-12, 12.1, 1.5)):
            for dx in np.arange(-3, 3.1, 1):
                for dy in np.arange(-3, 3.1, 1):
                    T = (aci0 + da, s, cx, cy, ox + dx, oy + dy); v = iou(don(T, dis_px), osm, .35)
                    if v > en[0]: en = (v, T)
    a, s, _, _, tx, ty = en[1]
    for _ in range(3):                                   # ince ayar
        for da in np.radians(np.arange(-1.2, 1.21, .4)):
            for ds in ([.985, 1, 1.015] if olcek_ara else [1]):
                for dx in np.arange(-.6, .61, .3):
                    for dy in np.arange(-.6, .61, .3):
                        T = (a + da, s * ds, cx, cy, tx + dx, ty + dy); v = iou(don(T, dis_px), osm, .2)
                        if v > en[0]: en = (v, T)
        a, s, _, _, tx, ty = en[1]
    return en[1], round(en[0], 3)

def vaziyet_donusumu(merkez_osm):
    """Ek-5 s.35 (2480×1754) blok merkezleri ↔ OSM merkezleri. Dönen fonksiyon pafta px → site m."""
    PLAN = {"B2": (833.2, 499.9), "B1": (1339.7, 499.9), "B3": (426.6, 759.9), "A": (1886.0, 540.0)}
    M, r = [], []
    for k, (u, v) in PLAN.items():
        X, Y = merkez_osm[k]; M += [[u, v, 1, 0], [-v, u, 0, 1]]; r += [X, Y]
    a, c, tx, ty = np.linalg.lstsq(np.array(M, float), np.array(r, float), rcond=None)[0]
    f = lambda u, v: [round(a * u + c * v + tx, 2), round(-a * v + c * u + ty, 2)]
    artik = {k: round(math.dist(f(*PLAN[k]), merkez_osm[k]), 2) for k in PLAN}
    return f, {"olcek_m_px": round(math.hypot(a, c), 4), "aci": round(math.degrees(math.atan2(c, a)), 2), "artik_m": artik}
