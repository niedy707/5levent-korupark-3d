#!/usr/bin/python3
"""Kat planlarından blok dış hattı + daire bölümleri → planlar.json (pafta pikseli).

Kaynak paftalar (data/ekler/sayfalar/, 150 dpi):
  B  (B1/B2/B3, 5 daire/kat) Ek-6 s.37 B1 zemin kat planı
  C7 (C1/C2/C3)              Ek-6 s.41 C1 2. kat planı (C3'ün 6 daireli katı s.45'te aynı dış hat; ortadaki alt daire
                             "alt-orta" = alt-orta-sol + alt-orta-sag birleşik → "bolum_genis")
  A  (8 daire/kat)           Ek-8 s.56 A blok "1. kat" (kanonda kat 2) — duvarlar silik, dış hat elle

Dış hat: koyu (doygunluğu düşük) çizgiler kapatılır, dışarıdan taşma doldurulur, en büyük kontur sadeleştirilir.
Daireler: konum adı → pafta pikselinde dikdörtgen/çokgen (göz ile planlardan, ±0,5 m); dış hatla kesişimi alınır,
geri kalan iç kısım "cekirdek" (merdiven, asansör, koridor) olur. Konum adları balkon/rapor/cephe-3d/konum.py ile aynı.

    /usr/bin/python3 araclar/site-3b/planlar-uret.py      # → araclar/site-3b/planlar.json (+ kontrol görseli scratch'e)
"""
import cv2, numpy as np, json, os, sys
KOK = os.path.dirname(os.path.abspath(__file__))
SAYFA = os.path.join(KOK, "../../data/ekler/sayfalar")

def R(x0, y0, x1, y1): return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
A_ORAN = 1.25    # s.56 gösterimden pafta pikseline (2490 px genişlik)
def a(*p): return [[round(x * A_ORAN), round(y * A_ORAN)] for x, y in p]

PLAN = {
  "B": {"sayfa": "s37-37", "kirp": (140, 575, 1110, 1210), "cm_px": 4.8585, "birim": {
      "ust-sol": R(130, 560, 505, 835),
      "ust-sag": R(745, 560, 1120, 835),
      "alt-sol": [[130, 790], [290, 790], [290, 870], [455, 870], [455, 1220], [130, 1220]],
      "alt-orta": R(455, 870, 795, 1220),
      "alt-sag": [[960, 790], [1120, 790], [1120, 1220], [795, 1220], [795, 870], [960, 870]]}},
  "C7": {"sayfa": "s41-41", "kirp": (150, 598, 1090, 1182), "cm_px": 4.8707, "birim": {
      "alt-sol": R(140, 875, 430, 1190), "alt-orta-sol": R(430, 965, 622, 1190), "alt-orta-sag": R(622, 965, 825, 1190),
      "alt-sag": R(825, 875, 1100, 1190), "ust-sag": R(825, 590, 1100, 875), "ust-orta": R(430, 590, 825, 790),
      "ust-sol": R(140, 590, 430, 875)}},
  "A": {"sayfa": "s56-56", "cm_px": None,
        "dis": a((500, 390), (660, 390), (660, 372), (770, 372), (770, 390), (935, 390), (935, 505), (1045, 505), (1045, 690),
                 (1120, 690), (1120, 810), (870, 810), (870, 830), (780, 830), (780, 810), (625, 810), (625, 695), (555, 695),
                 (555, 510), (500, 510)),
        "birim": {
      "ust-sol": a((490, 360), (660, 360), (660, 512), (490, 512)), "ust-orta": a((660, 360), (770, 360), (770, 512), (660, 512)),
      "ust-sag": a((770, 360), (940, 360), (940, 512), (770, 512)), "sag": a((935, 500), (1050, 500), (1050, 692), (935, 692)),
      "sol": a((540, 512), (655, 512), (655, 697), (540, 697)), "alt-sol": a((615, 697), (780, 697), (780, 840), (615, 840)),
      "alt-orta": a((780, 697), (920, 697), (920, 840), (780, 840)), "alt-sag": a((920, 685), (1130, 685), (1130, 840), (920, 840)),
      # kanon kat 2: alt-orta + alt-sag tek N tipi daire (4+1)
      "alt-sag-N": a((780, 685), (1130, 685), (1130, 840), (780, 840))},
        # zemin + asma kat ticari kaide (A-160…178), çatısı kat 2 terasları (11, 12, 13 ve büyük teras) — s.56 pembe + noktalı alan
        "kaide": a((935, 368), (1062, 365), (1300, 715), (1555, 1022), (1380, 1140), (1115, 870), (1120, 690), (1045, 690),
                   (1045, 505), (935, 505))},
}

def dis_hat(img, kirp):
    x0, y0, x1, y1 = kirp; sub = img[y0:y1, x0:x1]
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY); hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    koyu = ((g < 110) & (hsv[..., 1] < 80)).astype(np.uint8) * 255                 # renkli bahçe/teras dolguları hariç
    k = cv2.morphologyEx(koyu, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21)))
    k = cv2.copyMakeBorder(k, 2, 2, 2, 2, cv2.BORDER_CONSTANT, 0)
    ff = k.copy(); h, w = ff.shape; cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 128)
    dolu = np.where(ff == 128, 0, 255).astype(np.uint8)[2:-2, 2:-2]
    dolu = cv2.morphologyEx(dolu, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    cs, _ = cv2.findContours(dolu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 3.5, True)[:, 0, :]
    return [[int(x + x0), int(y + y0)] for x, y in c]

def bolumle(dis, birim, boyut):
    """Dış hat ∩ daire çokgenleri; çakışmada sözlük sırası kazanır (önce yazılan). Kalan iç kısım çekirdek."""
    h, w = boyut; M = np.zeros((h, w), np.uint8); cv2.fillPoly(M, [np.array(dis, np.int32)], 255)
    sahip = np.zeros((h, w), np.int16)          # 0 = çekirdek
    adlar = list(birim)
    for i, ad in reversed(list(enumerate(adlar, 1))):
        m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [np.array(birim[ad], np.int32)], 255); sahip[(m > 0)] = i
    cikti = {}
    for i, ad in enumerate([None] + adlar):
        m = ((sahip == i) & (M > 0)).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cs = [c for c in cs if cv2.contourArea(c) > 300]
        cikti[ad or "cekirdek"] = [[[int(x), int(y)] for x, y in cv2.approxPolyDP(c, 2.5, True)[:, 0, :]] for c in cs]
    return cikti

out = {}; gorseller = []
for tip, p in PLAN.items():
    img = cv2.imread(f"{SAYFA}/{p['sayfa']}.jpg")
    if img is None: sys.exit(f"sayfa yok: {p['sayfa']} — önce araclar/ekler-db-uret.py sayfaları basmalı")
    dis = p.get("dis") or dis_hat(img, p["kirp"])
    birim = dict(p["birim"])
    n_var = {}
    if tip == "C7":  # 3 ve 6 daireli katlar: alt orta tek daire
        bG = {k: v for k, v in birim.items() if k not in ("alt-orta-sol", "alt-orta-sag")}; bG["alt-orta"] = R(430, 965, 825, 1190)
        n_var = bolumle(dis, bG, img.shape[:2])
    if tip == "A":   # N tipi ayrı bölümleme (kanon kat 2)
        bN = {k: v for k, v in birim.items() if k not in ("alt-orta", "alt-sag", "alt-sag-N")}; bN["alt-sag-N"] = birim["alt-sag-N"]
        n_var = bolumle(dis, bN, img.shape[:2]); birim.pop("alt-sag-N")
    bol = bolumle(dis, birim, img.shape[:2])
    out[tip] = {"sayfa": p["sayfa"], "cm_px": p["cm_px"], "dis": dis, "bolum": bol}
    if n_var: out[tip]["bolum_N" if tip == "A" else "bolum_genis"] = n_var
    if "kaide" in p: out[tip]["kaide"] = p["kaide"]
    vis = img.copy(); renk = [(0, 0, 255), (0, 160, 0), (255, 0, 0), (0, 140, 255), (200, 0, 200), (0, 200, 200), (120, 60, 0), (90, 90, 90), (0, 0, 120)]
    cv2.polylines(vis, [np.array(dis, np.int32)], True, (0, 0, 0), 5)
    for i, (ad, cs) in enumerate(bol.items()):
        for c in cs:
            cv2.polylines(vis, [np.array(c, np.int32)], True, renk[i % len(renk)], 3)
            M = np.array(c).mean(0); cv2.putText(vis, ad, (int(M[0]) - 40, int(M[1])), cv2.FONT_HERSHEY_SIMPLEX, .8, renk[i % len(renk)], 2)
    if "kaide" in p: cv2.polylines(vis, [np.array(p["kaide"], np.int32)], True, (180, 0, 180), 3)
    xs = [x for x, y in dis]; ys = [y for x, y in dis]
    k = vis[max(0, min(ys) - 60):max(ys) + 60, max(0, min(xs) - 60):max(xs) + 60]
    if "kaide" in p: k = vis[max(0, min(ys) - 60):1500, max(0, min(xs) - 60):2000]
    gorseller.append(cv2.resize(k, (int(k.shape[1] * 600 / k.shape[0]), 600)))
    print(tip, "dış hat", len(dis), "nokta ·", {k: len(v) for k, v in bol.items()})
json.dump(out, open(f"{KOK}/planlar.json", "w", encoding="utf-8"), ensure_ascii=False)
kontrol = os.environ.get("KONTROL")
if kontrol: cv2.imwrite(kontrol, np.hstack(gorseller)); print("kontrol:", kontrol)
