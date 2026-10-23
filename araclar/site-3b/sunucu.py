#!/usr/bin/env python3
"""Korupark 3B — yerel önizleme sunucusu (port 3042, yalnız 127.0.0.1). Sitenin geri kalanından bağımsız:
yalnız public/site-3b.html ve public/assets/site-3b/ servis edilir. / ve /3d aynı sayfayı açar.

    python3 araclar/site-3b/sunucu.py          # http://127.0.0.1:3042/3d
"""
import http.server, os, sys
KOK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../public"))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3042
TUR = {".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8", ".js": "text/javascript; charset=utf-8",
       ".jpg": "image/jpeg", ".png": "image/png"}

class Isleyici(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        yol = self.path.split("?")[0].split("#")[0]
        if yol in ("/", "/3d", "/3d/"): dosya = os.path.join(KOK, "site-3b.html")
        elif yol.startswith("/assets/site-3b/"): dosya = os.path.normpath(os.path.join(KOK, yol.lstrip("/")))
        else: return self.send_error(404, "Not found", "Bu sunucu yalniz 3B sayfasini sunar")   # durum satiri latin-1: Turkce harf baglantiyi koparir
        if not dosya.startswith(os.path.join(KOK, "")) or not os.path.isfile(dosya): return self.send_error(404)
        veri = open(dosya, "rb").read()
        self.send_response(200); self.send_header("Content-Type", TUR.get(os.path.splitext(dosya)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(veri))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(veri)
    def log_message(self, *a): pass

print(f"Korupark 3B: http://127.0.0.1:{PORT}/3d")
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici).serve_forever()
