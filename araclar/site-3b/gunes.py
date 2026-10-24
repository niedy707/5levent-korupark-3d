"""Daire başına güneş alma süresi (haftalık) ve manzara açıklığı — gölge hesaplı.

Yöntem
- Örnek noktalar: her dairenin dış cephe kenarlarının (≥ 1,5 m) ortası, kat döşemesinin 1,5 m üstü, cepheden 0,4 m dışarıda.
- Engeller: 7 blok (dış hat, çatı + 1 m), A ticari kaide, komşu binalar (OSM yüksekliği ya da kat sayısı × 3 m). Arazi engel sayılmaz.
- Güneş konumu: NOAA yaklaşık formülleri (enlem 41,09°, boylam 28,94°, yerel saat UTC+3).
- Haftalık: 2026'nın her haftasının çarşambası, 05:00–21:00 arası 20 dakikalık adımlar. Güneş ufkun 2° üstünde, cephenin önünde ve
  noktadan güneşe giden ışını hiçbir engel kesmiyorsa o adım "güneşli". Dairenin herhangi bir cephe noktası güneşliyse daire güneş alır.
- Manzara: her noktadan cepheye dik yönün ±70°'sine 15 yatay ışın; ilk engelin uzaklığı (en çok 600 m) ortalaması; dairenin en iyi cephesi.
"""
import math
import numpy as np, cv2

ENLEM, BOYLAM, UTC = 41.0900, 28.9431, 3

def gunes_konumu(gun_no, saat_yerel):
    """Yılın günü (1…365) ve yerel saat → (azimut: kuzeyden saat yönüne derece, yükseklik derece)."""
    g = 2 * math.pi / 365 * (gun_no - 1 + (saat_yerel - UTC - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dek = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
           - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    gst = (saat_yerel * 60 + eqt + 4 * BOYLAM - 60 * UTC)
    ha = math.radians(gst / 4 - 180)
    lat = math.radians(ENLEM)
    cz = math.sin(lat) * math.sin(dek) + math.cos(lat) * math.cos(dek) * math.cos(ha)
    zen = math.acos(max(-1, min(1, cz)))
    az = math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(lat) - math.tan(dek) * math.cos(lat))) + 180
    return az % 360, 90 - math.degrees(zen)

def _engeller(bloklar, kaide, komsu):
    A, B, H = [], [], []
    def ekle(p, h):
        for i in range(len(p)):
            A.append(p[i]); B.append(p[(i + 1) % len(p)]); H.append(h)
    for b in bloklar: ekle(b["dis"], b["cati"] + 1.0)
    ekle(kaide["p"], kaide["ust"] + 1.0)
    for k in komsu:
        p = k["p"][:-1] if k["p"][0] == k["p"][-1] else k["p"]; ekle(p, k["z"] + k["h"])
    return np.array(A, float), np.array(B, float), np.array(H, float)

def _noktalar(bloklar):
    """Her dairenin dış cephe örnek noktaları → (P (N,3), n (N,2), sahip index (N,), kodlar)."""
    P, Nn, S, kodlar = [], [], [], []
    for b in bloklar:
        dis = np.array(b["dis"], np.float32)
        for kat in b["katlar"]:
            for kod, konum in kat["d"]:
                idx = len(kodlar); kodlar.append(kod)
                for poly, bay in zip(b["sablon"][konum], b["sablon_dis"][konum]):
                    for i in range(len(poly)):
                        if not bay[i]: continue
                        a, c = np.array(poly[i]), np.array(poly[(i + 1) % len(poly)]); L = np.linalg.norm(c - a)
                        if L < 1.5: continue
                        m = (a + c) / 2; n = np.array([-(c - a)[1], (c - a)[0]]) / L
                        if cv2.pointPolygonTest(dis, (float(m[0] + n[0] * .6), float(m[1] + n[1] * .6)), False) > 0: n = -n
                        q = m + n * 0.4
                        P.append([q[0], q[1], kat["kot"] + 1.5]); Nn.append(n); S.append(idx)
    return np.array(P), np.array(Nn), np.array(S), kodlar

def _ilk_engel(P, d, tan_alt, A, B, H):
    """Her nokta için d yönündeki ışının, yüksekliği tavanı aşmadan kestiği ilk engel kenarının uzaklığı (yoksa inf)."""
    AB = B - A                                  # (E,2)
    den = d[0] * AB[:, 1] - d[1] * AB[:, 0]     # (E,)
    ok = np.abs(den) > 1e-9; den = np.where(ok, den, 1)
    AP = A[None, :, :] - P[:, None, :2]         # (N,E,2)
    t = (AP[..., 0] * AB[:, 1] - AP[..., 1] * AB[:, 0]) / den
    u = (AP[..., 0] * d[1] - AP[..., 1] * d[0]) / den
    z = P[:, 2:3] + t * tan_alt
    hit = ok & (t > 0.05) & (u >= 0) & (u <= 1) & (z < H[None, :])
    return np.where(hit, t, np.inf).min(1)

def hesapla(bloklar, kaide, komsu, yil=2026):
    import datetime as dt
    P, Nn, S, kodlar = _noktalar(bloklar)
    A, B, H = _engeller(bloklar, kaide, komsu)
    nd = len(kodlar)
    # güneş: 52 hafta × 20 dk
    hafta = np.zeros((nd, 52), np.float32)
    maks = np.zeros(52, np.float32)        # gölgesiz, her yöne açık bir noktanın alabileceği en çok süre (güneş ufkun 2° üstünde)
    for w in range(52):
        gun = dt.date(yil, 1, 1) + dt.timedelta(days=7 * w + (2 - dt.date(yil, 1, 1).weekday()) % 7)
        gno = gun.timetuple().tm_yday
        for k in range(48):
            saat = 5 + (k + 0.5) / 3
            az, alt = gunes_konumu(gno, saat)
            if alt < 2: continue
            maks[w] += 1 / 3
            d = np.array([math.sin(math.radians(az)), math.cos(math.radians(az))])      # x doğu, y kuzey
            on = (Nn @ d) > 0.08
            if not on.any(): continue
            idx = np.where(on)[0]
            acik = np.isinf(_ilk_engel(P[idx], d, math.tan(math.radians(alt)), A, B, H))
            lit = np.zeros(nd, bool); lit[S[idx[acik]]] = True
            hafta[lit, w] += 1 / 3
    # manzara: cepheye dik ±70°, 15 yatay ışın, tavanı noktanın üstündeki engeller
    # vektörel: her yön için normalleri döndürüp gruplar hâlinde çöz (yön noktaya göre değiştiği için nokta başına)
    mesafe = np.zeros((len(P), 15))
    for j, off in enumerate(np.linspace(-70, 70, 15)):
        r = math.radians(off); c, s = math.cos(r), math.sin(r)
        D = np.stack([Nn[:, 0] * c - Nn[:, 1] * s, Nn[:, 0] * s + Nn[:, 1] * c], 1)
        # yöne göre kümele (5° kovalar): aynı d ile toplu çözüm
        aci = np.round(np.degrees(np.arctan2(D[:, 1], D[:, 0])) / 5).astype(int)
        for a_ in np.unique(aci):
            m = aci == a_; th = math.radians(a_ * 5); d = np.array([math.cos(th), math.sin(th)])
            t = _ilk_engel(P[m], d, 0.0, A, B, H)
            mesafe[m, j] = np.minimum(t, 600)
    nokta_ort = mesafe.mean(1)
    manzara = np.zeros(nd)
    np.maximum.at(manzara, S, nokta_ort)
    return kodlar, hafta, manzara, maks
