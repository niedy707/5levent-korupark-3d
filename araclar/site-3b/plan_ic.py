"""Daire iç planları: Yönetim Planı Ek-6 / Ek-8 paftaları (PDF'e gömülü 300 dpi tarama) → zemin dokusu + taşıyıcı duvarlar.

- Doku: paftanın bina bölgesi, gri tonlu, arka plan beyaza çekilmiş → public/assets/site-3b/plan-sNN.jpg
- Duvar: koyu (<100) piksellerden 9×9 açma ile yalnız kalın çizgiler (betonarme perde, dış duvar, çekirdek) kalır;
  bölme duvarı/kapı/mobilya ince çizgidir, dokuda görünür, 3B'ye çıkmaz. Kırıntılar (<350 px² ya da <40 px) atılır.
- Hizalama: her pafta kendi taban paftasına (B: s.37, C: s.41, A: s.56) faz korelasyonuyla kaydırılır; taban paftanın
  site dönüşümü (uret.py DONUSUM) kullanılır. 150 dpi pafta pikseli = 300 dpi / 2.
"""
import json, os, subprocess, tempfile
import numpy as np, cv2

PDF_ADI = "data/yonetim-plani/Yönetim planı Ekler (Ek-1 - Ek-8).pdf"
# sayfa → (taban tip, taban sayfa, 150 dpi kırpma kutusu)
SAYFALAR = {
    37: ("B", 37, (130, 560, 1120, 1220)),
    40: ("C7", 41, (140, 520, 1100, 1300)), 41: ("C7", 41, (140, 520, 1100, 1300)), 42: ("C7", 41, (140, 520, 1100, 1300)),
    44: ("C7", 41, (140, 520, 1100, 1300)), 45: ("C7", 41, (140, 520, 1100, 1300)),
    56: ("A", 56, (600, 440, 1600, 1160)),
}

def _sayfa_300(depo, no, gecici):
    on = os.path.join(gecici, f"s{no}")
    subprocess.run(["pdfimages", "-f", str(no), "-l", str(no), "-j", os.path.join(depo, PDF_ADI), on], check=True)
    return cv2.imread(f"{on}-000.jpg", cv2.IMREAD_GRAYSCALE)

def _kayma(taban, img, kutu):
    """img'in tabana göre kayması (300 dpi px), bina bölgesinde faz korelasyonu."""
    x0, y0, x1, y1 = [2 * v for v in kutu]
    a = taban[y0:y1, x0:x1].astype(np.float32); b = img[y0:y1, x0:x1].astype(np.float32)
    w = cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F)
    (dx, dy), guven = cv2.phaseCorrelate(a, b, w)
    return dx, dy, guven

def uret(depo, cikti, don_fn):
    """don_fn(tip, taban_sayfa, [(u150, v150)...]) → site noktaları (blok başına çağrılır, aşağıda değil uret.py'de).
    Burada yalnız sayfa başına doku + duvar (300 dpi kırpma pikseli) ve kırpma kökü/kayma üretilir."""
    out = {}
    meta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaynak", "plan-meta.json")
    if not os.path.exists(os.path.join(depo, PDF_ADI)):
        # PDF yoksa (ör. public kopya): dokular ve duvarlar daha önce üretilmiş hâlleriyle kullanılır
        m = json.load(open(meta, encoding="utf-8"))
        for no, v in m.items():
            v["duvar"] = json.load(open(f"{cikti}/plan-s{no}.json"))["duvar"]; out[int(no)] = v
        return out
    with tempfile.TemporaryDirectory() as g:
        imgs = {no: _sayfa_300(depo, no, g) for no in SAYFALAR}
        for no, (tip, taban_no, kutu) in SAYFALAR.items():
            img = imgs[no]
            dx, dy, guven = (0.0, 0.0, 1.0) if no == taban_no else _kayma(imgs[taban_no], img, kutu)
            x0, y0, x1, y1 = [2 * v for v in kutu]
            k = img[y0:y1, x0:x1]
            # doku: arka plan beyaz, çizgi koyu lacivert-gri; hafif kontrast
            d = cv2.normalize(k, None, 0, 255, cv2.NORM_MINMAX)
            d = np.clip((d.astype(np.float32) - 40) * 255 / 175, 0, 255).astype(np.uint8)
            renkli = cv2.merge([np.clip(d * 1.0 + 0, 0, 255).astype(np.uint8), np.clip(d * .98 + 2, 0, 255).astype(np.uint8),
                                np.clip(d * .95 + 6, 0, 255).astype(np.uint8)])
            cv2.imwrite(f"{cikti}/plan-s{no}.jpg", renkli, [cv2.IMWRITE_JPEG_QUALITY, 70, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
            # duvarlar
            m = (k < 100).astype(np.uint8) * 255
            o = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
            n, lab, st, _ = cv2.connectedComponentsWithStats(o); tut = np.zeros_like(o)
            for i in range(1, n):
                x, y, w, h, a = st[i]
                if max(w, h) >= 40 and a >= 350: tut[lab == i] = 255
            cs, hi = cv2.findContours(tut, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            duvar = []
            if hi is not None:
                hi = hi[0]
                for i, c in enumerate(cs):
                    if hi[i][3] != -1: continue            # delik; dışı ile birlikte yazılır
                    dis = cv2.approxPolyDP(c, 1.6, True)[:, 0, :].tolist()
                    if len(dis) < 3: continue
                    delik = []; j = hi[i][2]
                    while j != -1:
                        dl = cv2.approxPolyDP(cs[j], 1.6, True)[:, 0, :].tolist()
                        if len(dl) >= 3 and cv2.contourArea(cs[j]) > 30: delik.append(dl)
                        j = hi[j][0]
                    duvar.append([dis, delik] if delik else [dis])
            out[no] = {"tip": tip, "taban": taban_no, "kirp": [x0, y0], "boyut": [x1 - x0, y1 - y0], "kayma": [round(dx, 1), round(dy, 1)],
                       "guven": round(guven, 3), "duvar": duvar}
            json.dump({"sayfa": no, "duvar": duvar}, open(f"{cikti}/plan-s{no}.json", "w"), separators=(",", ":"))
    json.dump({str(k): {kk: vv for kk, vv in v.items() if kk != "duvar"} for k, v in out.items()}, open(meta, "w", encoding="utf-8"), separators=(",", ":"))
    return out
