#!/usr/bin/python3
"""Korupark 3B site modeli → public/site-3b.html + public/assets/site-3b/ (model.json, zemin dokuları).

Kaynaklar (hepsi bu depoda):
  data/blok-kat-daire/Korupark_blok_kat_daire.json   ⭐ kanon: blok / kat / daire numarası
  data/ekler/ek4-bagimsiz-bolumler.json              net/brüt m², arsa payı (malik yok)
  data/ekler/ek3-tahsis-listesi.json                 daire tipi (1+1 … 4+1)
  data/ekler/ekler-db.json                           tahsisli bahçe/teras kutuları (Ek-6) ve m²
  araclar/site-3b/planlar.json                       kat planı dış hatları + daire bölümleri (planlar-uret.py)
  data/ekler/sayfalar/s35-35.jpg                     Ek-5 45.15 kotu vaziyet planı (peyzaj, sahalar, havuz, otopark)
  araclar/site-3b/kaynak/osm.json                    OSM: blok izleri, yollar, komşu binalar (kaynak-hazirla.py)

Koordinat: metre, x doğu, y kuzey; orijin balkon 3B sayfasıyla aynı (41.090056, 28.943083).

    /usr/bin/python3 araclar/site-3b/uret.py            # (PIL/cv2/numpy/scipy yalnız sistem Python'unda)
"""
import json, math, os, sys, base64, hashlib, random
import numpy as np, cv2
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
KOK = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KOK)
DEPO = os.path.normpath(f"{KOK}/../..")
from hizala import don, blok_hizala, vaziyet_donusumu

KANON = json.load(open(f"{DEPO}/data/blok-kat-daire/Korupark_blok_kat_daire.json", encoding="utf-8"))["bloklar"]
EK4 = json.load(open(f"{DEPO}/data/ekler/ek4-bagimsiz-bolumler.json", encoding="utf-8"))
EK3 = {r["daire"]: r for r in json.load(open(f"{DEPO}/data/ekler/ek3-tahsis-listesi.json", encoding="utf-8"))}
EKDB = {p["sayfa"]: p for p in json.load(open(f"{DEPO}/data/ekler/ekler-db.json", encoding="utf-8"))["sayfalar"]}
PLAN = json.load(open(f"{KOK}/planlar.json", encoding="utf-8"))
OSM = json.load(open(f"{KOK}/kaynak/osm.json", encoding="utf-8"))
CIKTI = f"{DEPO}/public/assets/site-3b"; os.makedirs(CIKTI, exist_ok=True)
random.seed(5); np.random.seed(5)

# ───────────────────────── 1. bloklar: plan → site ─────────────────────────
BLOK_ID = {1314624447: "A", 1316673384: "B1", 1316673385: "B2", 1316673386: "B3", 1316673387: "C1", 1316673388: "C2", 1316673389: "C3"}
IZ = {BLOK_ID[b["id"]]: b["p"] for b in OSM["binalar"] if b["id"] in BLOK_ID}
TIP = {"A": "A", "B1": "B", "B2": "B", "B3": "B", "C1": "C7", "C2": "C7", "C3": "C7"}
# zemin kat (±0.00) kotları: Ek-6 pafta başlıkları. A'nınki paftada yok: B1 ile aynı varsayıldı (bahçe katı tutarlılığı, aşağıda).
ZEMIN = {"B1": 61.15, "B2": 58.15, "B3": 55.15, "C1": 51.65, "C2": 51.65, "C3": 51.65, "A": 61.15}
# C bloklarının kuzey yüzü alt katlarda toprak altında: ilk "üst sıra" dairesinin katı = bahçe kotu.
# C1 1. katta üst sıra var → bahçe 55.15 (= B3); C2 2. katta → 58.15 (= B2); C3 3. katta → 61.15 (= B1). Üç değer B kotlarıyla birebir tutuyor.
BAHCE_C = {"C1": 55.15, "C2": 58.15, "C3": 61.15}
def kat_kot(blok, kat): return ZEMIN[blok] + (0 if kat == 0 else 3.5 + 3.0 * (kat - 1))   # C1 2. kat +6.50, C3 3. kat +9.50 (Ek-6)
def kat_h(kat): return 3.5 if kat == 0 else 3.0

DONUSUM = {}
for b, t in TIP.items():
    p = PLAN[t]; s0 = (p["cm_px"] or 5.9) / 100
    (cx, cy), _, ang = cv2.minAreaRect(np.array(IZ[b], np.float32))
    a = ang - 90 * round(ang / 90)
    a0 = math.radians(a) + (math.pi / 2 if b == "B3" else 0)    # B3'ün planı 90° dönük (planın üstü batı)
    T, v = blok_hizala(p["dis"], IZ[b], a0, s0, olcek_ara=(t == "A"))
    DONUSUM[b] = T
    print(f"{b:3} plan→OSM örtüşme {v:.3f} · açı {math.degrees(T[0]):6.1f}° · ölçek {T[1] * 100:.3f} cm/px")

def poly_site(b, px): return don(DONUSUM[b], px)

# ───────────────────────── 2. kat düzeni (balkon/rapor/cephe-3d/konum.py ile aynı kural) ─────────────────────────
B5 = ["ust-sol", "alt-sol", "alt-orta", "alt-sag", "ust-sag"]
C7 = ["alt-sol", "alt-orta-sol", "alt-orta-sag", "alt-sag", "ust-sag", "ust-orta", "ust-sol"]
C6 = ["alt-sol", "alt-orta", "alt-sag", "ust-sag", "ust-orta", "ust-sol"]
A8 = ["sol", "alt-sol", "alt-orta", "alt-sag", "sag", "ust-sag", "ust-orta", "ust-sol"]
def duzen(b, n):
    if b.startswith("B"): return B5
    if b in ("C1", "C2", "C3"):
        if n == 4: return C7[:4]
        if n == 3: return C6[:3]
        if n == 6: return C6
        return C7
    if n == 4: return A8[:4]
    if n == 7: return ["sol", "alt-sol", "alt-sag-N", "sag", "ust-sag", "ust-orta", "ust-sol"]
    return A8
TAM = {"B": B5, "C7": C7, "A": A8}
def plan_sayfa(b, n):
    """Bu katın iç planı hangi paftadan: B s.37 · C zemin kendi paftası, 7 daireli s.41, 3/6 daireli s.45 · A s.56 (kanon kat 2)."""
    if b.startswith("B"): return 37
    if b == "A": return 56
    if n == 4: return {"C1": 40, "C2": 42, "C3": 44}[b]
    return 41 if n == 7 else 45
def cephe(b, konum):
    y = konum.split("-")[0]
    P = {"ust": "Kuzey", "alt": "Güney", "sol": "Batı", "sag": "Doğu"}
    if b == "B3": P = {"ust": "Batı", "alt": "Doğu", "sol": "Güney", "sag": "Kuzey"}
    return P[y]

# ───────────────────────── 3. Ek-4 / Ek-3 / Ek-6 bilgisi ─────────────────────────
E4 = {}
for r in EK4:
    E4[f"{r['blok']}-{r['bb_no']}"] = r
TAHSIS = {}   # daire → (tür, m², [site çokgeni], kot türü)
for s, p in EKDB.items():
    if p.get("ek") != "EK-6": continue
    for bg in p["bolgeler"]:
        for d in bg["daireler"]:
            TAHSIS.setdefault(d, []).append((s, bg["bbox_px"], bg.get("alan_m2"), "bahçe" if "BAHÇE" in bg["kategori"] else "teras"))

def yuvarla(p, n=2): return [[round(x, n), round(y, n)] for x, y in p]

def kenar_dis_mi(poly, dis):
    """Çokgenin her kenarı bloğun dış hattında mı (cephe) — pencere dokusu yalnız cephede."""
    D = np.array(dis, float); out = []
    for i in range(len(poly)):
        a = np.array(poly[i], float); b_ = np.array(poly[(i + 1) % len(poly)], float); m = (a + b_) / 2
        d = min(_nokta_kenar(m, D[j], D[(j + 1) % len(D)]) for j in range(len(D)))
        out.append(1 if d < 0.45 else 0)
    return out
def _nokta_kenar(p, a, b):
    ab = b - a; t = np.clip(np.dot(p - a, ab) / max(1e-9, np.dot(ab, ab)), 0, 1); return float(np.linalg.norm(p - (a + t * ab)))

bloklar = []; DAIRE = {}
for b in ["A", "B1", "B2", "B3", "C1", "C2", "C3"]:
    t = TIP[b]; P = PLAN[t]
    dis = poly_site(b, P["dis"])
    sablon = {}
    def ekle(kaynak, onek=""):
        for ad, cs in kaynak.items():
            if ad == "cekirdek": continue
            sablon[onek + ad if not onek else ad] = [yuvarla(poly_site(b, c)) for c in cs]
    ekle(P["bolum"])
    if t == "C7": sablon["alt-orta"] = [yuvarla(poly_site(b, c)) for c in P["bolum_genis"]["alt-orta"]]
    if t == "A": sablon["alt-sag-N"] = [yuvarla(poly_site(b, c)) for c in P["bolum_N"]["alt-sag-N"]]
    cekirdek = [yuvarla(poly_site(b, c)) for c in P["bolum"]["cekirdek"]]
    dis = yuvarla(dis)
    # cephe kenarları (pencere dokusu)
    sablon_dis = {k: [kenar_dis_mi(c, dis) for c in v] for k, v in sablon.items()}
    katlar = []
    for kat in sorted(KANON[b]["katlar"], key=lambda k: k["kat_no"]):
        L = duzen(b, len(kat["daireler"])); assert len(L) == len(kat["daireler"]), (b, kat)
        kullanilan = set(L) | ({"alt-orta-sol", "alt-orta-sag"} if "alt-orta" in L and t == "C7" else set()) \
                     | ({"alt-orta", "alt-sag"} if "alt-sag-N" in L else set())
        ortak = [k for k in TAM[t] if k not in kullanilan]
        katlar.append({"no": kat["kat_no"], "kot": round(kat_kot(b, kat["kat_no"]), 2), "h": kat_h(kat["kat_no"]),
                       "d": [[f"{b}-{n}", k] for n, k in zip(kat["daireler"], L)], "o": ortak,
                       "plan": plan_sayfa(b, len(kat["daireler"]))})
        for n, k in zip(kat["daireler"], L):
            kod = f"{b}-{n}"; e = E4.get(kod, {}); e3 = EK3.get(kod, {})
            bilgi = {"kat": kat["kat_no"], "cephe": cephe(b, k), "konum": k}
            if e.get("net_m2"): bilgi["net"] = e["net_m2"]
            if e.get("brut_m2"): bilgi["brut"] = e["brut_m2"]
            if e.get("arsa_payi"): bilgi["arsa"] = e["arsa_payi"]
            if e3.get("bb_tipi") and e3["bb_tipi"][0].isdigit(): bilgi["tip"] = e3["bb_tipi"]
            DAIRE[kod] = bilgi
    ust = max(katlar, key=lambda k: k["no"]); cati = round(ust["kot"] + ust["h"], 2)
    bloklar.append({"ad": b, "zemin": ZEMIN[b], "cati": cati, "dis": dis, "cekirdek": cekirdek, "sablon": sablon, "sablon_dis": sablon_dis,
                    "katlar": katlar, "aci": round(DONUSUM[b][0], 4), "merkez": [round(sum(x for x, y in dis) / len(dis), 1), round(sum(y for x, y in dis) / len(dis), 1)]})
    print(f"    {b}: {len(katlar)} kat, {sum(len(k['d']) for k in katlar)} daire, çatı +{cati}")
assert len(DAIRE) == sum(v["daire_sayisi"] for v in KANON.values()), "kanondaki her daire modelde olmalı"


# ───────────────────────── 3b. daire iç planları (Ek-6 / Ek-8, 300 dpi) ─────────────────────────
import plan_ic
PLAN_IC = plan_ic.uret(DEPO, CIKTI, None)
for no, p in PLAN_IC.items(): print(f"  iç plan s.{no}: {len(p['duvar'])} duvar parçası · kayma {p['kayma']} px (güven {p['guven']})")
def _afin(b, no):
    """Doku pikseli (300 dpi kırpma) → site: X = a·u + b·v + c, Y = d·u + e·v + f."""
    p = PLAN_IC[no]; x0, y0 = p["kirp"]; kx, ky = p["kayma"]
    def site(u, v): return don(DONUSUM[b], [((u + x0 - kx) / 2, (v + y0 - ky) / 2)])[0]
    o, ux, vy = np.array(site(0, 0)), np.array(site(1000, 0)), np.array(site(0, 1000))
    a_, d_ = (ux - o) / 1000; b_, e_ = (vy - o) / 1000
    return [round(float(a_), 7), round(float(b_), 7), round(float(o[0]), 3), round(float(d_), 7), round(float(e_), 7), round(float(o[1]), 3)]
for bl in bloklar:
    bl["plan"] = {str(no): _afin(bl["ad"], no) for no in sorted({k["plan"] for k in bl["katlar"]})}
PLANLAR_M = {str(no): {"doku": f"plan-s{no}.jpg", "duvar": f"plan-s{no}.json", "boyut": p["boyut"],
                       "ad": {37: "Ek-6 s.37 (B zemin kat)", 40: "Ek-6 s.40 (C1 zemin kat)", 41: "Ek-6 s.41 (C1 2. kat)", 42: "Ek-6 s.42 (C2 zemin kat)",
                              44: "Ek-6 s.44 (C3 zemin kat)", 45: "Ek-6 s.45 (C3 3. kat)", 56: "Ek-8 s.56 (A 2. kat)"}[no]} for no, p in PLAN_IC.items()}

# asansör ve yangın merdivenleri: kat planı çekirdeğinde elle okunan kutular (150 dpi pafta pikseli; A için 2490 px ölçeği)
# B s.37 · C s.41 · A s.56. Asansör: kabin kutuları (X işaretli); merdiven: basamaklı kovalar (ikisi de korunmuş, yangın merdiveni sayılır)
CEKIRDEK_OGE = {
    "B": {"asansor": [(627, 688, 672, 723), (627, 727, 672, 762), (612, 800, 668, 842)], "merdiven": [(512, 700, 582, 795), (680, 688, 742, 772)]},
    "C7": {"asansor": [(618, 825, 665, 860), (618, 862, 665, 900), (618, 902, 665, 940), (695, 822, 735, 872)], "merdiven": [(455, 822, 530, 945), (730, 822, 795, 945)]},
    "A": {"asansor": [(982, 695, 1022, 735), (982, 738, 1022, 778), (982, 780, 1022, 820)], "merdiven": [(865, 700, 935, 830), (1080, 720, 1145, 830)]},
}
for bl in bloklar:
    t = TIP[bl["ad"]]
    for tur, kutular in CEKIRDEK_OGE[t].items():
        bl[tur] = [yuvarla(poly_site(bl["ad"], [[x0, y0], [x1, y0], [x1, y1], [x0, y1]])) for x0, y0, x1, y1 in kutular]

# tahsisli bahçe / teras plakaları (Ek-6 kutuları; B blokları s.37–39, C zemin s.40/42/44, C üst s.41/45)
TAHSIS_PLAKA = []
SAYFA_PLAN = {37: "B", 38: "B", 39: "B", 40: "C7", 41: "C7", 42: "C7", 44: "C7", 45: "C7"}
for kod, liste in TAHSIS.items():
    b = kod.split("-")[0]
    for s, bb, m2, tur in liste:
        if s not in SAYFA_PLAN or b not in DONUSUM or TIP[b] != SAYFA_PLAN[s]: continue
        if s == 43: continue
        x0, y0, x1, y1 = bb
        kat = DAIRE[kod]["kat"] if kod in DAIRE else 0
        if kat == 0: tur = "bahçe"   # zemin kat tahsisleri bahçedir (Ek-6 C paftalarında "teras" yazsa da zeminde; kullanıcı, 24.10.2026)
        TAHSIS_PLAKA.append({"kod": kod, "tur": tur, "m2": m2, "kot": round(kat_kot(b, kat), 2), "p": yuvarla(poly_site(b, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))})
        if kod in DAIRE: DAIRE[kod]["tahsis"] = f"{tur} {str(m2).replace('.', ',')} m²" if m2 else tur

# A ticari kaide (zemin + asma kat işyerleri A-160…178; çatısı kat 2 terasları)
kaide = {"p": yuvarla(poly_site("A", PLAN["A"]["kaide"])), "taban": ZEMIN["A"], "ust": round(kat_kot("A", 2), 2),
         "bb": [f"A-{n}" for n in range(160, 179) if f"A-{n}" in E4 and E4[f"A-{n}"]["nitelik"] and "TRAFO" not in E4[f"A-{n}"]["nitelik"]]}
kaide["brut"] = round(sum(E4[k]["brut_m2"] or 0 for k in kaide["bb"]), 2)

# ───────────────────────── 4. vaziyet planı (Ek-5 s.35) → site ─────────────────────────
MERKEZ = {k: list(cv2.minAreaRect(np.array(v, np.float32))[0]) for k, v in IZ.items()}
VZ, vz_bilgi = vaziyet_donusumu(MERKEZ)
print("vaziyet planı → site:", vz_bilgi)
def vz(pts): return [VZ(u, v) for u, v in pts]
def dikdortgen(merkez, eksen, uzun, kisa):
    """Pafta merkezi + uzun eksen yönü (pafta) → site köşeleri, ölçüler metre."""
    c = np.array(VZ(*merkez)); e = np.array(VZ(merkez[0] + eksen[0], merkez[1] + eksen[1])) - c; e /= np.linalg.norm(e)
    n = np.array([-e[1], e[0]])
    return [list(np.round(c + e * sx * uzun / 2 + n * sy * kisa / 2, 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))], c, e

SAHALAR = []
# tenis: çit 36×18, kort 23,77×10,97 · futbol (halı saha): pafta köşelerinden · basketbol 28×15
_, c, e = dikdortgen((2187, 978), (-110, 170), 1, 1)
SAHALAR.append({"tur": "tenis", "merkez": list(np.round(c, 2)), "yon": [round(e[0], 4), round(e[1], 4)], "uzun": 34.0, "kisa": 17.0})
fk = vz([(2085, 1060), (2205, 1130), (2090, 1312), (1990, 1250)])
fc = np.mean(fk, 0); fe = (np.array(fk[2]) + np.array(fk[3])) / 2 - (np.array(fk[0]) + np.array(fk[1])) / 2
SAHALAR.append({"tur": "futbol", "merkez": list(np.round(fc, 2)), "yon": list(np.round(fe / np.linalg.norm(fe), 4)),
                "uzun": round(float(np.linalg.norm(fe)), 1), "kisa": round(float(np.linalg.norm(np.array(fk[1]) - np.array(fk[0]))), 1)})
bk = vz([(1803, 1318), (1993, 1318), (1993, 1412), (1803, 1412)])
bc = np.mean(bk, 0); be = (np.array(bk[1]) + np.array(bk[2])) / 2 - (np.array(bk[0]) + np.array(bk[3])) / 2
SAHALAR.append({"tur": "basketbol", "merkez": list(np.round(bc, 2)), "yon": list(np.round(be / np.linalg.norm(be), 4)), "uzun": 28.0, "kisa": 15.0})

# havuz (cevre-uret.py ile aynı köşeler; kulvarlı ana havuz) + çocuk havuzu (taralı)
KIRP = (980, 1180)
SU = [(225, 120), (538, 118), (541, 200), (335, 238), (225, 195)]
GUVERTE = [(95, 115), (600, 105), (592, 180), (562, 215), (458, 246), (350, 262), (214, 216), (95, 135)]
HAVUZ = {"su": vz([(u + KIRP[0], v + KIRP[1]) for u, v in SU]), "guverte": vz([(u + KIRP[0], v + KIRP[1]) for u, v in GUVERTE]),
         "cocuk": vz([(1470, 1305), (1528, 1300), (1530, 1395), (1480, 1418), (1470, 1360)])}
# şezlonglar: güverte kuzey kenarı boyunca ve batı ucunda (pafta s.35'teki çiftler)
SEZLONG = []
for u in range(1060, 1480, 22): SEZLONG.append(VZ(u, 1308) + [0])
for v in range(1325, 1400, 20): SEZLONG.append(VZ(1095, v) + [1])
# kafe terası şemsiyeleri (sosyal tesis önü, pafta 1580–1660 × 1280–1360)
SEMSIYE = [VZ(u, v) for u, v in [(1592, 1290), (1622, 1300), (1652, 1292), (1600, 1325), (1632, 1335), (1660, 1322), (1612, 1355), (1642, 1362)]]

# otoparklar (açık): kuzey (A önü) ve doğu şeridi (A yolunun dışı)
OTOPARK = [{"p": vz([(1755, 245), (2015, 245), (2015, 375), (1755, 375)]), "sira": [[VZ(1810, 275), VZ(1995, 275)], [VZ(1770, 350), VZ(2000, 350)]]},
           {"p": vz([(1995, 330), (2085, 330), (2250, 610), (2250, 720), (2190, 720), (1995, 400)]),
            "sira": [[VZ(2030, 360), VZ(2210, 690)], [VZ(2085, 340), VZ(2250, 640)]]}]
# rampa (otoparka iniş, A ile B1 arası) ve dönel kavşak göbekleri
RAMPA = [vz([(1592, 380), (1660, 380), (1660, 556), (1592, 556)])]
GOBEK = [{"m": VZ(2100, 860), "r": 7.6}, {"m": VZ(180, 952), "r": 6.4}]
# oyun alanları (Ek-5: B2–B3 arası ve A önü; batıdaki taralı alan B3 96–98'e tahsisli oyun alanı)
OYUN = [{"ad": "Oyun alanı", "p": vz([(565, 640), (725, 640), (765, 700), (745, 835), (560, 835)])},
        {"ad": "Oyun alanı", "p": vz([(1555, 690), (1700, 690), (1810, 735), (1800, 850), (1560, 850)])},
        {"ad": "Oyun alanı (B3 96–98'e tahsisli)", "p": vz([(110, 995), (200, 1000), (300, 1100), (405, 1225), (110, 1225)])}]
# podyum: 45.15 kotu otoparkın çatısı (C bloklarının zemini, +51.65) — vaziyet planındaki kalın çizgi; havuz güvertesi güneyde bitişik
PODYUM = vz([(505, 858), (1965, 858), (1965, 1250), (1720, 1292), (1560, 1300), (1560, 1430), (1050, 1440), (1050, 1295),
             (560, 1290), (470, 1225), (390, 1130), (345, 1010), (360, 940), (505, 940)])
# arazide sabit tutulan kısım: C bloklarının orta çizgisinin güneyi (bloklar arası geçitler bahçeden podyuma eğimle iner)
PODYUM_SABIT = vz([(505, 1005), (1965, 1005), (1965, 1250), (1720, 1292), (560, 1290), (470, 1225), (390, 1130), (345, 1010)])
# havuz ve sosyal tesis önü otoparkın +45.15 kotunda (otopark-kat-eslesme.json: C3 −2 "Sosyal Tesis & Havuz"), podyumun güneyinde
HAVUZ_KOT = 45.15
HAVUZ_ALAN = vz([(985, 1266), (1712, 1266), (1712, 1380), (1560, 1440), (985, 1445)])   # duvarın 1,5 m kuzeyinden: eğim duvarın arkasında kalır
# bahçe (B ile C arası, B kotlarından C kuzey kotlarına iner)
BAHCE = vz([(420, 560), (1965, 560), (1965, 858), (505, 858), (505, 940), (420, 940)])
# B3 batısındaki teraslı işyerleri (3. bodrum, 45.15 kotu) önü
B3_TICARI = vz([(200, 600), (275, 600), (275, 1000), (200, 1000)])

# ───────────────────────── 5. yollar ve alanlar (OSM) ─────────────────────────
HALKA_ID = 1470076629
# Halka yolun C blokları önündeki parçası podyum (+51,65) üstünde, havuzun kuzeyinde ilerler (uydu görüntüsü: yol, istinat duvarı, altta havuz).
# OSM çizgisi burada havuz güvertesinin üstüne düşüyor (≈5 m güneyde): pafta v 1260–1360 arasındaki noktalar duvarın kuzeyine (v 1268) alınır,
# kafe binasının doğusundan dönmesi için bir ara nokta eklenir.
def _ters_vz(x, y):
    o = np.array(VZ(0, 0)); M_ = np.array([np.array(VZ(1, 0)) - o, np.array(VZ(0, 1)) - o]).T
    return np.linalg.solve(M_, np.array([x, y]) - o)
for w in OSM["yollar"]:
    if w["id"] != HALKA_ID: continue
    yeni = []
    for x, y in w["p"]:
        u, v = _ters_vz(x, y)
        if 1000 < u < 1700 and 1255 < v < 1360: yeni.append(VZ(u, 1255))
        else:
            if 1780 < u < 1830 and 1320 < v < 1360 and yeni: yeni.append(VZ(1745, 1257))
            yeni.append([x, y])
    w["p"] = yeni
# İstinat duvarı (podyum +51,65 → havuz +45,15), kafe/sosyal tesis cephesi, asansör kulesi ve merdiven (Ek-5 s.35'ten)
DUVAR = {"beton": vz([(985, 1291), (1600, 1291)]), "cam": vz([(1600, 1291), (1712, 1291)]),
         "asansor": vz([(1714, 1293), (1738, 1293), (1738, 1317), (1714, 1317)]),
         "merdiven": vz([(1740, 1293), (1772, 1293), (1772, 1337), (1740, 1337)]), "ust": 51.65, "alt": 45.15,
         # duvarın hemen kuzeyindeki şerit: arazi ızgarası (3 m) duvar çizgisinde basamak yapmasın diye podyum kotunda düz döşeme
         "serit": vz([(985, 1262), (1712, 1262), (1712, 1291), (985, 1291)])}
YOL_GEN = {"motorway": 13, "motorway_link": 6.5, "trunk": 11, "primary": 9, "primary_link": 5.5, "secondary": 8, "secondary_link": 5,
           "tertiary": 7, "unclassified": 6, "residential": 6, "service": 4.5, "footway": 2.2, "pedestrian": 3, "steps": 2.2, "cycleway": 2}
yollar = []
for w in OSM["yollar"]:
    h = w["t"].get("highway")
    if h not in YOL_GEN: continue
    if w["t"].get("tunnel") == "yes" or str(w["t"].get("layer", "0")).startswith("-"): continue
    gen = YOL_GEN[h]
    if w["id"] == HALKA_ID: gen = 6.5
    elif h == "service" and w["t"].get("service") == "parking_aisle": gen = 5
    yollar.append({"id": w["id"], "h": h, "gen": gen, "ad": w["t"].get("name", ""), "p": w["p"], "tek": w["t"].get("oneway") == "yes"})
HALKA = next(w["p"] for w in OSM["yollar"] if w["id"] == HALKA_ID)
SITE = next(a["p"] for a in OSM["alanlar"] if a["t"].get("name") == "5. Levent Korupark Sitesi")

# ───────────────────────── 6. arazi (kot) ─────────────────────────
# Izgara 3 m; sabit hücreler: blok tabanları, podyum, havuz güvertesi, halka yol profili, dış sınır.
# Serbest hücreler Laplace denklemiyle doldurulur (düzgün, tümsek yapmayan yüzey). Dış çevre yaklaşık bir eğim düzlemidir.
AX0, AY0, AD, ANX, ANY = -450.0, -330.0, 3.0, 261, 234        # x −450…330, y −330…369
def dis_duzlem(x, y): return 50.0 + 0.055 * y + 0.012 * x      # kuzey (15 Temmuz Cd.) ≈ 57, güney (FSM Blv.) ≈ 40
gx = AX0 + np.arange(ANX) * AD; gy = AY0 + np.arange(ANY) * AD
GX, GY = np.meshgrid(gx, gy)
H = dis_duzlem(GX, GY); SABIT = np.zeros(H.shape, bool)
SABIT[0, :] = SABIT[-1, :] = SABIT[:, 0] = SABIT[:, -1] = True
def hucre_maske(poly, genlet=0):
    m = np.zeros(H.shape, np.uint8)
    cv2.fillPoly(m, [np.array([[(x - AX0) / AD, (y - AY0) / AD] for x, y in poly], np.int32)], 1)
    if genlet: m = cv2.dilate(m, np.ones((2 * genlet + 1, 2 * genlet + 1), np.uint8))
    return m.astype(bool)
def sabitle(mask, deger):
    H[mask] = deger if np.isscalar(deger) else deger[mask]; SABIT[mask] = True

# dış yollar: eğim düzleminde kalsın (site çevresinden uzaktakiler)
site_m = hucre_maske(SITE)
# halka yol profili: site merkezine göre açıya bağlı (kuzey B girişleri, güney otopark girişi)
YC = (-40.0, 0.0)
PROFIL = [(0, 54.5), (39, 61.15), (90, 61.15), (128, 58.15), (158, 55.15), (183, 50.0), (214, 46.5), (248, 51.65), (336, 51.65), (360, 54.5)]   # güney kolu podyumda (+51,65)
def halka_kot(x, y):
    a = math.degrees(math.atan2(y - YC[1], x - YC[0])) % 360
    for (a0, h0), (a1, h1) in zip(PROFIL, PROFIL[1:]):
        if a0 <= a <= a1: return h0 + (h1 - h0) * (a - a0) / (a1 - a0)
    return PROFIL[0][1]
def cizgi_maske(pts, gen):
    m = np.zeros(H.shape, np.uint8)
    cv2.polylines(m, [np.array([[(x - AX0) / AD, (y - AY0) / AD] for x, y in pts], np.int32)], False, 1, max(1, int(round(gen / AD))))
    return m.astype(bool)
hm = cizgi_maske(HALKA + HALKA[:1], 8)
HK = np.vectorize(halka_kot)(GX, GY); sabitle(hm, HK)
for w in yollar:   # halkaya bağlanan kollar: halka kotunda
    if w["h"] == "service" and w["id"] != HALKA_ID and any(site_m[int((y - AY0) / AD), int((x - AX0) / AD)] for x, y in w["p"]
                                                         if 0 <= int((y - AY0) / AD) < ANY and 0 <= int((x - AX0) / AD) < ANX):
        m = cizgi_maske(w["p"], 5) & ~SABIT; sabitle(m, HK)
sabitle(hucre_maske(PODYUM_SABIT), 51.65)
sabitle(hucre_maske(HAVUZ_ALAN), HAVUZ_KOT)
sabitle(hucre_maske(B3_TICARI), 46.15)
for b in bloklar:
    m = hucre_maske(b["dis"], 1)
    if b["ad"] in BAHCE_C:      # C: kuzey yarısı bahçe kotunda, güney yarısı podyumda
        aci = b["aci"]; vy = np.array([-math.sin(aci), math.cos(aci)])   # planın "üst"ü
        c = np.array(b["merkez"]); ust = ((GX - c[0]) * vy[0] + (GY - c[1]) * vy[1]) > 0
        sabitle(m & ust, BAHCE_C[b["ad"]]); sabitle(m & ~ust, 51.65)
    else: sabitle(m, b["zemin"])
sabitle(hucre_maske(kaide["p"]), ZEMIN["A"])
# sahalar ve açık otoparklar düz döşenir: yanındaki halka yolun kotunda
for sh in SAHALAR:
    e = np.array(sh["yon"]); n = np.array([-e[1], e[0]]); c = np.array(sh["merkez"]); U, V = sh["uzun"] / 2 + 2, sh["kisa"] / 2 + 2
    sabitle(hucre_maske([c - e * U - n * V, c + e * U - n * V, c + e * U + n * V, c - e * U + n * V]), halka_kot(*c))
for o in OTOPARK: c = np.mean(o["p"], 0); sabitle(hucre_maske(o["p"]) & ~SABIT, halka_kot(*c))
# komşu sitelerin yolları / binaları düzlemde; FSM ve 15 Temmuz düzlemde (sabit)
for w in yollar:
    if w["h"] in ("primary", "secondary", "motorway", "primary_link", "secondary_link", "motorway_link", "tertiary"):
        m = cizgi_maske(w["p"], w["gen"] + 4) & ~site_m; sabitle(m, dis_duzlem(GX, GY))
# Laplace çözümü
idx = -np.ones(H.shape, int); serbest = np.argwhere(~SABIT); idx[tuple(serbest.T)] = np.arange(len(serbest))
A = lil_matrix((len(serbest), len(serbest))); rhs = np.zeros(len(serbest))
for k, (i, j) in enumerate(serbest):
    A[k, k] = 4
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ii, jj = i + di, j + dj
        if idx[ii, jj] >= 0: A[k, idx[ii, jj]] = -1
        else: rhs[k] += H[ii, jj]
H[tuple(serbest.T)] = spsolve(A.tocsr(), rhs)
print(f"arazi: {ANX}×{ANY} hücre, serbest {len(serbest)} · kot {H.min():.1f}…{H.max():.1f}")
H_TABAN = 30.0
arazi = {"x0": AX0, "y0": AY0, "d": AD, "nx": ANX, "ny": ANY, "taban": H_TABAN,
         "h": base64.b64encode(np.clip((H - H_TABAN) * 100, 0, 65535).astype("<u2").tobytes()).decode()}
def kot(x, y):
    fx, fy = (x - AX0) / AD, (y - AY0) / AD; i, j = int(fy), int(fx); tx, ty = fx - j, fy - i
    i = min(max(i, 0), ANY - 2); j = min(max(j, 0), ANX - 2)
    return float(H[i, j] * (1 - tx) * (1 - ty) + H[i, j + 1] * tx * (1 - ty) + H[i + 1, j] * (1 - tx) * ty + H[i + 1, j + 1] * tx * ty)

# ───────────────────────── 7. zemin dokusu (iç: 0,25 m/px · dış: 1 m/px) ─────────────────────────
RENK = {  # BGR
    "dis": (150, 172, 160), "cim": (112, 170, 128), "cim2": (98, 158, 116), "tas": (196, 214, 224), "tas2": (180, 200, 212),
    "asfalt": (112, 110, 104), "asfalt2": (128, 126, 120), "serit": (235, 240, 244), "kaldirim": (200, 206, 210), "orman": (88, 128, 92),
    "konut": (186, 192, 194), "okul": (170, 196, 214), "guverte": (168, 196, 214), "bitki": (78, 128, 84), "oyun": (150, 178, 226),
    "oyun2": (150, 196, 222), "otopark": (122, 120, 114), "kavsak": (100, 160, 110)}
class Doku:
    def __init__(s, x0, y0, x1, y1, r, zemin):
        s.x0, s.y0, s.x1, s.y1, s.r = x0, y0, x1, y1, r
        s.W, s.Hh = int(round((x1 - x0) / r)), int(round((y1 - y0) / r))
        s.img = np.zeros((s.Hh, s.W, 3), np.uint8); s.img[:] = zemin
        s.sinif = np.zeros((s.Hh, s.W), np.uint8)    # ağaç yerleşimi için: 1 çim, 2 sert zemin, 3 bitki
    def px(s, pts): return np.array([[(x - s.x0) / s.r, (s.y1 - y) / s.r] for x, y in pts], np.float32)
    def doldur(s, poly, renk, sinif=None):
        p = np.round(s.px(poly) * 8).astype(np.int32)
        cv2.fillPoly(s.img, [p], renk, cv2.LINE_AA, 3)
        if sinif is not None: cv2.fillPoly(s.sinif, [np.round(s.px(poly)).astype(np.int32)], sinif)
    def cizgi(s, pts, renk, gen_m, kapali=False, sinif=None):
        p = np.round(s.px(pts) * 8).astype(np.int32); g = max(1, int(round(gen_m / s.r)))
        cv2.polylines(s.img, [p], kapali, renk, g, cv2.LINE_AA, 3)
        if sinif is not None: cv2.polylines(s.sinif, [np.round(s.px(pts)).astype(np.int32)], kapali, sinif, g)
    def kesik(s, pts, renk, gen_m, dolu=3.0, bos=6.0):
        P = np.array(pts, float)
        for a, b_ in zip(P, P[1:]):
            L = np.linalg.norm(b_ - a); d = (b_ - a) / max(L, 1e-9); t = 0
            while t < L: s.cizgi([a + d * t, a + d * min(L, t + dolu)], renk, gen_m); t += dolu + bos
    def kaydet(s, yol, kalite=82):
        cv2.imwrite(yol, s.img, [cv2.IMWRITE_JPEG_QUALITY, kalite, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])

def yol_ciz(D, ayrinti):
    adli = []
    for w in sorted(yollar, key=lambda w: w["gen"]):
        if w["h"] in ("footway", "steps", "pedestrian", "cycleway"):
            D.cizgi(w["p"], RENK["kaldirim"], w["gen"], sinif=2); continue
        D.cizgi(w["p"], RENK["asfalt2"], w["gen"] + 1.2, sinif=2)     # bordür/omuz
    for w in sorted(yollar, key=lambda w: w["gen"]):
        if w["h"] in ("footway", "steps", "pedestrian", "cycleway"): continue
        D.cizgi(w["p"], RENK["asfalt"], w["gen"], sinif=2)
        if ayrinti and w["gen"] >= 6 and w["h"] != "service":
            if w["tek"]: D.kesik(w["p"], RENK["serit"], .15, 3, 7)      # tek yönlü çok şeritli yol: şerit çizgisi
            else: D.kesik(w["p"], RENK["serit"], .15, 4, 5)
        if ayrinti and w["id"] == HALKA_ID: D.kesik(w["p"] + w["p"][:1], RENK["serit"], .12, 2, 4)

def alan_ciz(D):
    for a in OSM["alanlar"]:
        t = a["t"]
        if a["p"][0] != a["p"][-1] and len(a["p"]) < 4: continue
        if t.get("landuse") in ("grass",) or t.get("leisure") == "park" or t.get("natural") == "grassland": D.doldur(a["p"], RENK["cim2"], 1)
        elif t.get("landuse") == "forest" or t.get("natural") == "wood": D.doldur(a["p"], RENK["orman"], 3)
        elif t.get("landuse") == "residential" and t.get("name") != "5. Levent Korupark Sitesi": D.doldur(a["p"], RENK["konut"], 2)
        elif t.get("amenity") == "school": D.doldur(a["p"], RENK["okul"], 2)
        elif t.get("amenity") == "parking": D.doldur(a["p"], RENK["otopark"], 2)
        elif t.get("landuse") == "religious": D.doldur(a["p"], RENK["tas"], 2)

def site_ic_ciz(D, ayrinti):
    D.doldur(SITE, RENK["cim"], 1)
    D.doldur(BAHCE, RENK["cim"], 1)
    D.doldur(PODYUM, RENK["tas"], 2); D.doldur(HAVUZ_ALAN, RENK["tas2"], 2)
    D.doldur(B3_TICARI, RENK["tas2"], 2)
    # vaziyet planı çizgileri bahçeye: ince çizgiler patika/sınır (taş rengi), sık taralı yerler bitki (koyu yeşil)
    if ayrinti:
        im = cv2.imread(f"{DEPO}/data/ekler/sayfalar/s35-35.jpg", cv2.IMREAD_GRAYSCALE)
        src = np.float32([[0, 0], [2480, 0], [0, 1754]]); dst = np.float32([[(VZ(u, v)[0] - D.x0) / D.r, (D.y1 - VZ(u, v)[1]) / D.r] for u, v in src])
        M = cv2.getAffineTransform(src, dst)
        cizgi = cv2.warpAffine((im < 150).astype(np.uint8) * 255, M, (D.W, D.Hh), flags=cv2.INTER_LINEAR)
        yogun = cv2.blur(cizgi.astype(np.float32), (9, 9)) > 95          # taralı dolgular (şev / bitki adası)
        bm = np.zeros((D.Hh, D.W), np.uint8); cv2.fillPoly(bm, [np.round(D.px(BAHCE)).astype(np.int32)], 1)
        for o in OYUN[:2]: cv2.fillPoly(bm, [np.round(D.px(o["p"])).astype(np.int32)], 0)
        bm = bm.astype(bool)
        ac = (cizgi > 110) & bm
        D.img[ac & ~yogun] = RENK["tas"]; D.sinif[ac & ~yogun] = 2
        D.img[yogun & bm] = RENK["bitki"]; D.sinif[yogun & bm] = 3
    for o in OYUN: D.doldur(o["p"], RENK["oyun"] if o is not OYUN[2] else RENK["oyun2"], 2)
    for p in OTOPARK:
        D.doldur(p["p"], RENK["otopark"], 2)
        if ayrinti:
            for a, b_ in p["sira"]:         # park yeri çizgileri, 2,5 m arayla, yola dik 5 m
                a, b_ = np.array(a), np.array(b_); L = np.linalg.norm(b_ - a); e = (b_ - a) / L; n = np.array([-e[1], e[0]])
                for t in np.arange(0, L, 2.5): q = a + e * t; D.cizgi([q - n * 2.5, q + n * 2.5], RENK["serit"], .12)
    for r in RAMPA: D.doldur(r, RENK["asfalt"], 2)
    D.doldur(HAVUZ["guverte"], RENK["guverte"], 2)
    for g in GOBEK:
        D.cizgi([[g["m"][0] + (g["r"] + 2) * math.cos(t), g["m"][1] + (g["r"] + 2) * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 40)], RENK["asfalt"], 3, True)
        D.doldur([[g["m"][0] + g["r"] * math.cos(t), g["m"][1] + g["r"] * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 40)], RENK["kavsak"], 3)
    # blok çevresi: 3 m taş döşeme
    for b in bloklar: D.cizgi(b["dis"] + b["dis"][:1], RENK["tas2"], 6, True, 2)
    for t in TAHSIS_PLAKA:
        D.doldur(t["p"], RENK["cim2"] if t["tur"] == "bahçe" else RENK["tas2"], 1 if t["tur"] == "bahçe" else 2)
    # sahalar
    for s in SAHALAR:
        e = np.array(s["yon"]); n = np.array([-e[1], e[0]]); c = np.array(s["merkez"])
        R_ = lambda u, v: list(c + e * u + n * v)
        kut = lambda U, V: [R_(-U, -V), R_(U, -V), R_(U, V), R_(-U, V)]
        if s["tur"] == "tenis":
            D.doldur(kut(s["uzun"] / 2 + 1, s["kisa"] / 2 + 1), (70, 110, 180), 2)                 # dış: kiremit
            D.doldur(kut(23.77 / 2 + 1.5, 10.97 / 2 + 1), (150, 110, 60), 2)                        # kort: mavi akrilik
            W = (240, 244, 246)
            D.cizgi(kut(23.77 / 2, 10.97 / 2), W, .1, True); D.cizgi([R_(-11.885, -4.115), R_(11.885, -4.115)], W, .08)
            D.cizgi([R_(-11.885, 4.115), R_(11.885, 4.115)], W, .08); D.cizgi([R_(-6.4, 0), R_(6.4, 0)], W, .08)
            D.cizgi([R_(-6.4, -4.115), R_(-6.4, 4.115)], W, .08); D.cizgi([R_(6.4, -4.115), R_(6.4, 4.115)], W, .08)
        elif s["tur"] == "futbol":
            U, V = s["uzun"] / 2, s["kisa"] / 2; D.doldur(kut(U, V), (70, 150, 80), 2)
            for k in range(-int(U), int(U), 4): D.doldur([R_(k, -V + .6), R_(k + 2, -V + .6), R_(k + 2, V - .6), R_(k, V - .6)], (80, 162, 92), 2)
            W = (238, 242, 242); D.cizgi(kut(U - .6, V - .6), W, .12, True); D.cizgi([R_(0, -V + .6), R_(0, V - .6)], W, .12)
            D.cizgi([R_(3 * math.cos(t), 3 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 30)], W, .12, True)
            for sg in (-1, 1): D.cizgi([R_(sg * (U - .6), -5), R_(sg * (U - 5.5), -5), R_(sg * (U - 5.5), 5), R_(sg * (U - .6), 5)], W, .12)
        else:
            U, V = s["uzun"] / 2, s["kisa"] / 2; D.doldur(kut(U + 1, V + 1), (120, 110, 100), 2); D.doldur(kut(U, V), (70, 110, 190), 2)
            for sg in (-1, 1): D.doldur([R_(sg * U, -2.45), R_(sg * (U - 5.8), -2.45), R_(sg * (U - 5.8), 2.45), R_(sg * U, 2.45)], (150, 100, 50), 2)
            W = (240, 244, 246); D.cizgi(kut(U, V), W, .08, True); D.cizgi([R_(0, -V), R_(0, V)], W, .08)
            D.cizgi([R_(1.8 * math.cos(t), 1.8 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 30)], W, .08, True)
            for sg in (-1, 1):
                D.cizgi([R_(sg * (U - 1.575 - 6.75 * math.cos(t)), 6.75 * math.sin(t)) for t in np.linspace(-math.pi / 2, math.pi / 2, 30)], W, .08)
    D.doldur(HAVUZ["su"], (190, 170, 60), 4); D.doldur(HAVUZ["cocuk"], (200, 180, 80), 4)

ic = Doku(-240, -205, 140, 140, 0.25, RENK["dis"])
alan_ciz(ic); site_ic_ciz(ic, True); yol_ciz(ic, True)
ic.kaydet(f"{CIKTI}/zemin-ic.jpg", 80)
dis = Doku(-450, -330, 330, 369, 1.0, RENK["dis"])
alan_ciz(dis); site_ic_ciz(dis, False); yol_ciz(dis, False)
dis.img = cv2.GaussianBlur(dis.img, (3, 3), 0); dis.kaydet(f"{CIKTI}/zemin-dis.jpg", 78)
print("zemin dokuları:", ic.W, "×", ic.Hh, "·", dis.W, "×", dis.Hh)

# ───────────────────────── 8. ağaçlar ─────────────────────────
agac = []    # [x, y, z, tür, ölçek]  tür: 0 yuvarlak taçlı, 1 servi/çam, 2 çalı
def uygun(x, y, D=ic, sinif=(1,), bosluk=2.5):
    j, i = int((x - D.x0) / D.r), int((D.y1 - y) / D.r)
    if not (0 <= i < D.Hh and 0 <= j < D.W): return False
    k = int(bosluk / D.r); pencere = D.sinif[max(0, i - k):i + k + 1, max(0, j - k):j + k + 1]
    return D.sinif[i, j] in sinif and (pencere == D.sinif[i, j]).all()
bina_m = np.zeros((ic.Hh, ic.W), np.uint8)
for b in bloklar: cv2.fillPoly(bina_m, [np.round(ic.px(b["dis"])).astype(np.int32)], 1)
cv2.fillPoly(bina_m, [np.round(ic.px(kaide["p"])).astype(np.int32)], 1)
for s in SAHALAR:
    e = np.array(s["yon"]); n = np.array([-e[1], e[0]]); c = np.array(s["merkez"]); U, V = s["uzun"] / 2 + 3, s["kisa"] / 2 + 3
    cv2.fillPoly(bina_m, [np.round(ic.px([c - e * U - n * V, c + e * U - n * V, c + e * U + n * V, c - e * U + n * V])).astype(np.int32)], 1)
cv2.fillPoly(bina_m, [np.round(ic.px(HAVUZ["guverte"])).astype(np.int32)], 1)
bina_m = cv2.dilate(bina_m, np.ones((17, 17), np.uint8)).astype(bool)
def poisson(maske_fn, x0, y0, x1, y1, r, deneme=6000):
    pts = []; hucre = r / math.sqrt(2); G = {}
    for _ in range(deneme):
        x, y = random.uniform(x0, x1), random.uniform(y0, y1)
        if not maske_fn(x, y): continue
        gi, gj = int(x / hucre), int(y / hucre)
        if any(math.dist((x, y), G[(gi + a, gj + b)]) < r for a in range(-2, 3) for b in range(-2, 3) if (gi + a, gj + b) in G): continue
        G[(gi, gj)] = (x, y); pts.append((x, y))
    return pts
def bina_yok(x, y):
    j, i = int((x - ic.x0) / ic.r), int((ic.y1 - y) / ic.r)
    return 0 <= i < ic.Hh and 0 <= j < ic.W and not bina_m[i, j]
# site içi çimler (bahçe ve çevre şevleri): seyrek, yer yer kümeli
for x, y in poisson(lambda x, y: uygun(x, y, ic, (1,), 2.0) and bina_yok(x, y), -240, -205, 140, 140, 7.5, 26000):
    agac.append([x, y, 1 if random.random() < .28 else 0, random.uniform(.8, 1.25)])
# bitki adaları (taralı): çalı
for x, y in poisson(lambda x, y: uygun(x, y, ic, (3,), .5) and bina_yok(x, y), -240, -205, 140, 140, 2.2, 9000):
    agac.append([x, y, 2, random.uniform(.7, 1.2)])
# halka yol boyunca dış kenarda ağaç dizisi (her ~11 m)
P = np.array(HALKA + HALKA[:1], float); L = 0
for a, b_ in zip(P, P[1:]):
    d = np.linalg.norm(b_ - a); e = (b_ - a) / max(d, 1e-9); n = np.array([e[1], -e[0]])    # sağ el = dışarı (saat yönünün tersi halka)
    t = (11 - L % 11)
    while t < d:
        for yan in (1, -1):
            q = a + e * t + n * yan * 6.2
            if uygun(q[0], q[1], ic, (1,), 1.0) and bina_yok(*q): agac.append([float(q[0]), float(q[1]), 1 if yan > 0 else 0, random.uniform(.9, 1.15)])
        t += 11
    L += d
# OSM ormanı ve dış çimler (dış doku, seyrek): yalnız iç dokunun dışında kalanlar
for x, y in poisson(lambda x, y: (not (-240 < x < 140 and -205 < y < 140)) and uygun(x, y, dis, (3,), 2) , -450, -330, 330, 369, 9, 9000):
    agac.append([x, y, 0 if random.random() < .6 else 1, random.uniform(1, 1.5)])
for x, y in poisson(lambda x, y: (-240 < x < 140 and -205 < y < 140) and uygun(x, y, ic, (3,), 2) and not site_m[int((y - AY0) / AD), int((x - AX0) / AD)], -240, -205, 140, 140, 6, 9000):
    agac.append([x, y, 0 if random.random() < .65 else 1, random.uniform(1, 1.45)])
agac = [a for a in agac if math.hypot(a[0] + 11.6, a[1] - 88.5) > 16]   # giriş kapısının önü/ardı açık
agac = [[round(x, 1), round(y, 1), round(kot(x, y), 2), t, round(s, 2)] for x, y, t, s in agac]
print("ağaç:", len(agac), {t: sum(a[3] == t for a in agac) for t in (0, 1, 2)})

# ───────────────────────── 9. komşu binalar ─────────────────────────
komsu = []
for w in OSM["binalar"]:
    if w["id"] in BLOK_ID or len(w["p"]) < 4: continue
    t = w["t"]; p = w["p"][:-1] if w["p"][0] == w["p"][-1] else w["p"]
    cx, cy = np.mean(p, 0)
    if not (-450 < cx < 330 and -330 < cy < 369): continue
    # site sınırı içindeki OSM "building"leri (spor sahalarının yeri) komşu değil — sahalar vaziyet planından çizilir
    if cv2.pointPolygonTest(np.array(SITE, np.float32), (float(cx), float(cy)), False) > 0: continue
    if t.get("height"): yuk = float(str(t["height"]).split()[0])
    elif t.get("building:levels"): yuk = float(t["building:levels"]) * 3.0
    else:
        yuk = {"apartments": 39, "school": 12, "mosque": 14, "industrial": 9, "roof": 4}.get(t.get("building"), 9)
        if t.get("name") == "A1": yuk = 66
    z = min(kot(x, y) for x, y in p)
    komsu.append({"p": yuvarla(p, 1), "z": round(z, 2), "h": yuk, "t": t.get("building")})
print("komşu bina:", len(komsu))


# ───────────────────────── 9b. otopark (Ek-3 krokileri → site) ─────────────────────────
# Krokilerdeki kesikli blok izleri (B2, B1: +45.15 paftası; C1: +54.65 paftası) ↔ OSM izlerinin alan merkezleri, en küçük kareler.
# Beş pafta aynı CAD sayfasından: aralarındaki kayma faz korelasyonuyla ölçülür (≤ 9 px ≈ 0,6 m) ve düzeltilir.
OTO = json.load(open(f"{DEPO}/data/otopark/otopark-db.json", encoding="utf-8"))
OTO_ES = json.load(open(f"{DEPO}/data/blok-kat-daire/otopark-kat-eslesme.json", encoding="utf-8"))["bloklar"]
KROKI = f"{DEPO}/public/assets/krokiler"
def _kroki_iz(k, kutu):
    im = cv2.imread(f"{KROKI}/{k}_1.jpg", 0); x0, y0, x1, y1 = kutu; sub = im[y0:y1, x0:x1]
    d = cv2.morphologyEx((sub < 140).astype(np.uint8) * 255, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31)))
    d = cv2.copyMakeBorder(d, 2, 2, 2, 2, cv2.BORDER_CONSTANT, 0); ff = d.copy(); h, w = ff.shape
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 128)
    f = np.where(ff == 128, 0, 255).astype(np.uint8)[2:-2, 2:-2]
    cs, _ = cv2.findContours(f, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); M = cv2.moments(max(cs, key=cv2.contourArea))
    return M["m10"] / M["m00"] + x0, M["m01"] / M["m00"] + y0
def _alan_merkez(p): M = cv2.moments(np.array(p, np.float32)); return M["m10"] / M["m00"], M["m01"] / M["m00"]
KR_IZ = {"B2": ("45.15", (1288, 760, 2018, 1211)), "B1": ("45.15", (2312, 760, 3042, 1211)), "C1": ("54.65", (1272, 1878, 1971, 2406))}
Mk, rk = [], []
for b, (k, kutu) in KR_IZ.items():
    u, v = _kroki_iz(k, kutu); X, Y = _alan_merkez(IZ[b]); Mk += [[u, v, 1, 0], [-v, u, 0, 1]]; rk += [X, Y]
ka, kc, ktx, kty = np.linalg.lstsq(np.array(Mk, float), np.array(rk, float), rcond=None)[0]
kroki_artik = {b: round(math.dist([ka * u + kc * v + ktx, -ka * v + kc * u + kty], _alan_merkez(IZ[b])), 2)
               for b, (k, kutu) in KR_IZ.items() for u, v in [_kroki_iz(k, kutu)]}
KOTLAR = ["45.15", "48.15", "51.65", "54.65", "57.65"]
def _kucuk(k): return cv2.resize(cv2.imread(f"{KROKI}/{k}_1.jpg", 0), (1242, 879)).astype(np.float32)
_ref = _kucuk("45.15"); KAYMA = {k: (0.0, 0.0) if k == "45.15" else tuple(4 * x for x in cv2.phaseCorrelate(_ref, _kucuk(k))[0]) for k in KOTLAR}
def kroki_site(k, u, v):
    u, v = u - KAYMA[k][0], v - KAYMA[k][1]
    return [round(ka * u + kc * v + ktx, 2), round(-ka * v + kc * u + kty, 2)]
print(f"kroki → site: ölçek {math.hypot(ka, kc) * 100:.2f} cm/px · açı {math.degrees(math.atan2(kc, ka)):.2f}° · artık (m) {kroki_artik} · kayma (px) "
      + ", ".join(f"{k}:{x:.0f}/{y:.0f}" for k, (x, y) in KAYMA.items()))
# kat dokuları: paftanın plan alanı (başlık bandı hariç), 2800 px genişlik; köşeler sitede (paralelkenar)
KR_KIRP = (93, 605, 4858, 3088)
oto_kat = {}
for k in KOTLAR:
    x0, y0, x1, y1 = KR_KIRP; im = cv2.imread(f"{KROKI}/{k}_1.jpg")[y0:y1, x0:x1]
    W = 2800; im = cv2.resize(im, (W, int(round(im.shape[0] * W / im.shape[1]))), interpolation=cv2.INTER_AREA)
    cv2.imwrite(f"{CIKTI}/otopark-{k}.jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 72, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    oto_kat[k] = {"dosya": f"otopark-{k}.jpg", "kose": [kroki_site(k, x0, y0), kroki_site(k, x1, y0), kroki_site(k, x1, y1), kroki_site(k, x0, y1)]}
import otopark_yon
HUCRE = otopark_yon.hucre_acilari(OTO["yerler"], KROKI)       # yer → aracın uzun ekseni, kroki pikselinde (derece, y aşağı)
kutu_eksen = {k["kutu"]: k["eksen"] for k in OTO["kutular"]}
oto_yer = {}
for y in OTO["yerler"]:
    x_, y_ = kroki_site(y["kot"], y["x_px"], y["y_px"])
    a = HUCRE.get(y["yer"])
    if a is None: a = 90.0 if kutu_eksen.get(y["kutu"], "x") == "x" else 0.0   # yedek: yan yana dizili → araç dik eksende
    u, v = math.cos(math.radians(a)), math.sin(math.radians(a))
    fi = math.atan2(-ka * v + kc * u, ka * u + kc * v)        # aracın uzun ekseni, sitede (x doğu, y kuzey)
    oto_yer[y["yer"]] = [x_, y_, KOTLAR.index(y["kot"]), round(fi + math.pi / 2, 3), {"normal": 0, "engelli": 1, "elektrikli": 2}.get(y["tip"], 0),
                         y["daire"] or ""]
print(f"otopark yönü: {sum(1 for v in HUCRE.values() if v is not None)}/{len(OTO['yerler'])} yer krokideki hücresinden ya da komşu hücrelerden")
oto_daire = {d["daire"]: d["yerler"] for d in OTO["daireler"] if d["yerler"]}
for kod, yl in oto_daire.items():
    if kod in DAIRE: DAIRE[kod]["oto"] = yl
RENK_HEX = {"Turuncu": "#f97316", "Yeşil": "#16a34a", "Kırmızı": "#dc2626", "Mavi": "#2563eb", "Mor": "#7c3aed"}
_renkler = json.load(open(f"{DEPO}/data/blok-kat-daire/otopark-kat-eslesme.json", encoding="utf-8"))["renkler"]
OTOPARK_M = {"renk": {v["kot"].lstrip("+"): {"ad": ad, "hex": RENK_HEX[ad]} for ad, v in _renkler.items()}, "kotlar": KOTLAR, "kat": oto_kat, "yer": oto_yer, "eslesme": {b: {v["kot"].lstrip("+"): int(k) for k, v in x.items()} for b, x in OTO_ES.items()},
             "not": "Ek-3 krokileri; yer konumu kalibrasyon merkezi (±15 cm), pafta hizası ±0,6 m"}
print("otopark:", len(oto_yer), "yer ·", sum(1 for d in DAIRE.values() if "oto" in d), "dairenin yeri var")

# ───────────────────────── 10. etiketler, sınır, yazma ─────────────────────────
def merkez(p): return [round(float(np.mean([q[0] for q in p])), 1), round(float(np.mean([q[1] for q in p])), 1)]
etiket = [{"ad": "Havuz", "p": merkez(HAVUZ["su"]), "tur": "su"}]
for s in SAHALAR: etiket.append({"ad": {"tenis": "Tenis kortu", "futbol": "Halı saha", "basketbol": "Basketbol"}[s["tur"]], "p": s["merkez"], "tur": "saha"})
for o in OYUN[:2]: etiket.append({"ad": o["ad"], "p": merkez(o["p"]), "tur": "oyun"})
etiket.append({"ad": "Kafe terası", "p": merkez(SEMSIYE), "tur": "oyun"})
# komşu yerleşimler — adlar kullanıcıdan (23.10.2026); konum OSM alan/bina merkezleri
KOMSU_AD = [("Bayramoğlu Sitesi", (-114, -128)), ("Mimar Sinan İlköğretim Okulu", (-244, 11)), ("Finanskent Sitesi", (-420, 62)),
            ("5.Levent 1.Etap", (235, 40))]
for ad, p in KOMSU_AD: etiket.append({"ad": ad, "p": list(p), "tur": "site"})
adlar = {}
for w in yollar:
    if w["ad"] and w["h"] in ("primary", "secondary", "motorway", "tertiary"): adlar.setdefault(w["ad"], []).extend(w["p"])
for ad, pts in adlar.items():
    if "Kavşağı" in ad: continue
    x, y = min(pts, key=lambda p: math.hypot(p[0] + 40, p[1] - 0))
    etiket.append({"ad": ad, "p": [round(x, 1), round(y, 1)], "tur": "yol"})

model = {
    "meta": {"ad": "5. Levent Korupark · 3B site modeli", "uretim": __import__("datetime").date.today().isoformat(),
             "kaynak": "Daire yerleri ve kat planları: Yönetim Planı Ek-4, Ek-6, Ek-8 + blok/kat/daire kanonu; peyzaj, havuz, sahalar, otopark: "
                       "Yönetim Planı Ek-5 vaziyet planı; blok izleri, yollar, komşu binalar © OpenStreetMap katkıcıları (ODbL)",
             "uyari": "Kotlar ve peyzaj yaklaşık; ölçülmüş rölöve değildir.",
             "vaziyet": vz_bilgi, "zemin": ZEMIN},
    "arazi": arazi,
    "doku": {"ic": {"dosya": "zemin-ic.jpg", "k": [ic.x0, ic.y0, ic.x1, ic.y1]}, "dis": {"dosya": "zemin-dis.jpg", "k": [dis.x0, dis.y0, dis.x1, dis.y1]}},
    "bloklar": bloklar, "kaide": kaide, "planlar": PLANLAR_M, "daire": DAIRE, "tahsis": TAHSIS_PLAKA,
    "havuz": {**{k: yuvarla(v) for k, v in HAVUZ.items()}, "kot": HAVUZ_KOT}, "sezlong": [[round(a, 1), round(b_, 1), c] for a, b_, c in SEZLONG],
    "semsiye": yuvarla(SEMSIYE, 1), "sahalar": [{**s, "z": round(kot(*s["merkez"]), 2)} for s in SAHALAR], "gobek": GOBEK,
    "podyum": yuvarla(PODYUM), "site": yuvarla(SITE), "agac": agac, "komsu": komsu, "etiket": etiket,
    "halka": yuvarla(HALKA), "otopark": OTOPARK_M, "duvar": {k: (yuvarla(v) if isinstance(v, list) else v) for k, v in DUVAR.items()},
    # site girişi (B1 ile A arası, 15 Temmuz Cd. bağlantısı; OSM giriş/çıkış kolları 1470076630/31'in ortası): "Korupark" kapısı
    "kapi": {"merkez": [-11.6, 88.5], "yon": [round(math.cos(math.radians(9.5)), 4), round(math.sin(math.radians(9.5)), 4)], "gen": 21.0, "z": round(kot(-11.6, 88.5), 2)},
}
yol = f"{CIKTI}/model.json"
json.dump(model, open(yol, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("model:", yol, round(os.path.getsize(yol) / 1024), "KB")

# sayfa kendi başına durur (başka sayfaya bağlı değil): three.js ve simge kendi klasöründe
import shutil
shutil.copyfile(f"{DEPO}/balkon/rapor/video-komsu-1410/vendor/three.min.js" if os.path.exists(f"{DEPO}/balkon/rapor/video-komsu-1410/vendor/three.min.js")
                else f"{DEPO}/public/assets/vendor/three.min.js", f"{CIKTI}/three.min.js")
shutil.copyfile(f"{DEPO}/public/assets/ikon-192.png", f"{CIKTI}/ikon.png")
# sayfa: şablon + sürüm özeti (önbellek kırma)
surum = hashlib.md5(b"".join(open(f"{CIKTI}/{f}", "rb").read() for f in ("model.json", "zemin-ic.jpg", "zemin-dis.jpg", *[f"otopark-{k}.jpg" for k in KOTLAR], *[f"plan-s{n}.{e}" for n in PLAN_IC for e in ("jpg", "json")]))).hexdigest()[:8]
sablon = open(f"{KOK}/sablon.html", encoding="utf-8").read()
assert sablon.count("/*SURUM*/") == 1
open(f"{DEPO}/public/site-3b.html", "w", encoding="utf-8").write(sablon.replace("/*SURUM*/", surum))
print("sayfa: public/site-3b.html · sürüm", surum)
