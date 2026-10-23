"""Otopark yerinin yönü: Ek-3 krokisinde yerin numarasını çevreleyen park hücresinin dikdörtgeni.

Yer numarası (kalibrasyon noktası) hücrenin üst kenarındadır. Numaranın biraz altından (birkaç aday tohum) beyaz alan
taşma ile doldurulur; dolgunun dışbükey zarfının en küçük dikdörtgeni hücredir. Uzun kenar = aracın boyu.
Reddedilenler: kareye yakın (yön belirsiz), zarf dikdörtgeni doldurmuyor (çizgi boşluğundan sızma), çok küçük/büyük.
Bulunamayanlar aynı kottaki ~9 m içindeki komşuların açı ortalamasını (180° periyotlu) alır.
"""
import math
import numpy as np, cv2

TOHUM = [(0, 13), (0, 16), (-6, 13), (6, 13), (-13, 22), (13, 22), (-13, 32), (13, 32), (0, 58), (-12, 45), (12, 45), (-10, 8), (10, 8)]

def hucre_acilari(yerler, kroki_dizini):
    im, out = {}, {}
    for y in yerler:
        k = y["kot"]
        if k not in im:
            h = cv2.cvtColor(cv2.imread(f"{kroki_dizini}/{k}_1.jpg"), cv2.COLOR_BGR2HSV)
            im[k] = cv2.erode(((h[..., 2] > 205) & (h[..., 1] < 38)).astype(np.uint8), np.ones((2, 2), np.uint8))   # beyaz; ince çizgi boşlukları kapanır
        B = im[k]; x, yy = int(round(y["x_px"])), int(round(y["y_px"])); en = None
        for sx, sy in TOHUM:
            X, Y = x + sx, yy + sy
            if not (110 <= X < B.shape[1] - 110 and 110 <= Y < B.shape[0] - 110) or not B[Y, X]: continue
            sub = B[Y - 110:Y + 110, X - 110:X + 110].copy(); m = np.zeros((222, 222), np.uint8)
            n, _, _, (rx, ry, rw, rh) = cv2.floodFill(sub, m, (110, 110), 2, flags=4 | (255 << 8))
            if n < 350 or n > 6000 or rw > 130 or rh > 130: continue
            cs, _ = cv2.findContours((m[1:-1, 1:-1] > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            c = cv2.convexHull(np.vstack(cs)); A = cv2.contourArea(c); r = cv2.minAreaRect(c); w, h = r[1]
            if min(w, h) < 12 or max(w, h) < 1.35 * min(w, h) or A < 0.82 * w * h: continue
            P = cv2.boxPoints(r); e1, e2 = P[1] - P[0], P[2] - P[1]; e = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2
            en = round(math.degrees(math.atan2(e[1], e[0])) % 180, 1); break
        out[y["yer"]] = en
    konum = {y["yer"]: (y["kot"], y["x_px"], y["y_px"]) for y in yerler}
    for n, a in list(out.items()):
        if a is not None: continue
        k, x, yy = konum[n]
        v = [out[m] for m, (k2, x2, y2) in konum.items() if k2 == k and out[m] is not None and math.hypot(x2 - x, y2 - yy) < 130]
        if v:
            s = sum(math.sin(math.radians(2 * t)) for t in v); c = sum(math.cos(math.radians(2 * t)) for t in v)
            out[n] = round((math.degrees(math.atan2(s, c)) / 2) % 180, 1)
    return out
