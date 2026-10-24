# Korupark 3B site modeli — `korupark.5-levent.com/3d` (23.10.2026)

Komşuların siteyi incelemesi için etkileşimli 3B model: 7 blok, 744 daire (her biri tıklanabilir), daire iç planları, otopark yerleri, havuz, sahalar,
peyzaj, çevre yolları ve komşu binalar. Herkese açıktır; kişisel veri yoktur (malik adı, telefon yok).

| Çıktı | Ne |
|---|---|
| `public/site-3b.html` | Sayfa (şablon `sablon.html` + sürüm özeti). `vercel.json`: `/3d` → bu dosya |
| `public/assets/site-3b/model.json` | Bloklar, kat/daire çokgenleri, Ek-4/Ek-3 bilgisi, arazi kotları, ağaçlar, komşular, otopark yerleri |
| `public/assets/site-3b/zemin-{ic,dis}.jpg` | Zemin dokusu (vaziyet planı + OSM'den boyanmış) |
| `public/assets/site-3b/plan-sNN.{jpg,json}` | Daire iç planı dokusu (300 dpi pafta) + taşıyıcı duvarlar; yalnız "Kat planı" açılınca yüklenir |
| `public/assets/site-3b/otopark-<kot>.jpg` | Ek-3 kroki dokusu; yalnız "Otopark katı" açılınca yüklenir |

**Sayfa ve dosyalar elle düzenlenmez** — üreteç koşturulur:

```bash
/usr/bin/python3 araclar/site-3b/planlar-uret.py   # kat planı dış hatları + daire bölümleri → planlar.json (yalnız plan kutuları değişince)
python3 araclar/site-3b/kaynak-hazirla.py          # OSM → kaynak/osm.json (yalnız OSM tazelenecekse)
/usr/bin/python3 araclar/site-3b/uret.py           # her şey → public/ (PIL/cv2/numpy/scipy yalnız sistem Python'unda)
python3 araclar/site-3b/sunucu.py                 # yerel önizleme: http://127.0.0.1:3042/3d (yalnız bu sayfa)
```

## Kaynaklar ve yöntem

- **Daire yeri:** kanon (`data/blok-kat-daire/`) + `balkon/rapor/cephe-3d/konum.py` ile aynı kural (Ek-4 m² dizisi her
  katta aynı; numaralama saat yönünün tersine). Kat düzeni `uret.py` → `duzen()`.
- **Daire biçimi:** Ek-6 s.37 (B), s.41 (C), Ek-8 s.56 (A) kat planlarının dış hattı (koyu çizgi + taşma doldurma; A elle) ve
  daire kutuları (`planlar-uret.py`). Plan → OSM bina izi hizalaması örtüşme (IoU) en büyüklenerek: A 0,90 · B 0,87 · C 0,90.
- **İç plan:** PDF'e gömülü 300 dpi taramalar (`pdfimages`, yeniden örnekleme yok). Paftalar taban paftaya faz korelasyonuyla
  kaydırılır (≤ 10 px ≈ 25 cm). Duvarlar: koyu piksel + 9×9 açma → yalnız betonarme perde/dış duvar 3B'ye çıkar; bölme
  duvarı, kapı, mobilya dokuda görünür. Kat → pafta: B s.37 · C zemin s.40/42/44 · C 7 daireli s.41 · C 3/6 daireli s.45 · A s.56.
  A'da 8 daireli katlarda alt orta + alt sağ paftada tek (N tipi) görünür.
- **Kotlar:** zemin ±0.00 kotları Ek-6 başlıklarından (B1 61.15 · B2 58.15 · B3 55.15 · C 51.65; **A paftada yok, 61.15 varsayıldı**).
  C bloklarının kuzey yüzü alt katlarda toprak altında: ilk üst sıra dairenin katı bahçe kotunu verir (C1 55.15 · C2 58.15 ·
  C3 61.15) — B kotlarıyla birebir tutuyor. Kat yüksekliği zemin 3,5 m, diğerleri 3,0 m (Ek-6: C1 2. kat +6.50, C3 3. kat +9.50).
  Havuz +45.15 (otopark-kat-eslesme.json: C3 −2 "Sosyal Tesis & Havuz"). Arazi: sabit kotlar + Laplace (3 m ızgara); dış çevre
  yaklaşık eğim düzlemi. **Ölçülmüş rölöve değildir.**
- **Peyzaj/havuz/sahalar/otopark alanları:** Ek-5 s.35 vaziyet planı → site (blok merkezleriyle benzerlik dönüşümü, artık ≤ 1,1 m);
  uydu görüntüsüyle çakıştırılarak kontrol edildi (havuz, halka yol, sahalar oturuyor).
- **Otopark:** `data/otopark/otopark-db.json` yer noktaları; kroki → site dönüşümü krokilerdeki kesikli blok izleriyle (artık ≤ 0,6 m),
  beş pafta arası kayma faz korelasyonuyla. Kontrol: +45.15 noktaları ayrıca hizalanan Ek-5 paftasındaki park çizgilerine düşüyor.
  **Araç yönü** krokideki hücrenin dikdörtgeninden (`otopark_yon.py`); okunamayan ~%1,5 komşu hücrelerin yönünü alır.
  Kot renkleri `otopark-kat-eslesme.json` (Turuncu +57.65 … Mor +45.15); "kaçıncı kat" o bloğun asansör numarasıdır.

## Arayüz

- Blok düğmesi (üstte) → blok odağa gelir, yanında "daire no" kutusu; panelde arama, blok/kat/daire seçicileri; modelde tıklama.
- Bağlantı: `/3d#C3-88` daireyi seçili açar.
- **Kat planı:** seçili katın üstü kesilir, dairelerin iç planı zeminde + duvarlar 3B; ▲▼ ile kat değişir.
- **Otopark katı:** kroki o kotta yarı saydam açılır, yerler kot renginde araçla işaretlenir; kartta "Otoparka nasıl gidilir"
  (daire katı, otopark katı + renk, numaralar, asansörden yön/mesafe — kuş uçuşu).
- Sayfanın amacı komşuların siteyi incelemesi; anket/imza işaretlemesi arayüzde yok (gerekirse `model.json` veritabanı olarak kullanılır).

## Bağımsız sayfa (23.10.2026)

kullanıcı: "başlı başına tek başına bir sayfa olsun, başka bir sayfa ile bağlantısız". Sayfa sitenin geri kalanına link vermez;
three.js ve simge `public/assets/site-3b/` içinde kendi kopyası. Sol üstteki ⌂ bu sayfanın ana görünümüne döner ve seçimi sıfırlar.
Telefonda bilgi kartı alttan açılır (seçim yokken gizli), ⤢ Genişlet ile neredeyse tam ekran olur.

Kaynaklar ve sınırlar yalnız sağ üstteki **ℹ️ Hakkında** penceresinde yazılır (kullanıcı: "başka yerde olmasın"); sayfanın altında
yalnız zorunlu "GYO ya da Site yönetimi ile bağlantısı yoktur" satırı kalır. OSM atıfı da Hakkında'dadır.

## Havuz önündeki kot farkı (24.10.2026)

Uydu görüntüsü: halka yol C bloklarının önünde podyum kotunda (+51,65) ilerler, havuz bir istinat duvarıyla ayrılmış altta (+45,15).
OSM halka çizgisi burada havuz güvertesine düşüyordu (≈5 m güney) — `uret.py` bu parçayı duvarın kuzeyine alır, yol profili güney
kolunda +51,65'tir. Duvar, kafe cam cephesi, korkuluk, asansör kulesi ve merdiven `DUVAR` (Ek-5 s.35 pafta pikselinden).
Arazi ızgarası 3 m: duvar çizgisinde basamak yapmasın diye havuz kotu duvarın ~3 m kuzeyinden başlar, aradaki şerit podyum kotunda düz döşemedir.

## Public GitHub kopyası (24.10.2026)

<https://github.com/niedy707/5levent-korupark-3d> — kullanıcı kararıyla public. **Kaynak burasıdır; kopya elle düzenlenmez.**
Değişiklikten sonra: `bash araclar/site-3b/yayin-kopyala.sh` (dosyaları `~/Projects/5levent-korupark-3d`'ye kopyalar, yorumlardaki
kişi adını "kullanıcı"ya çevirir, ad/e-posta/IP/anahtar denetimi yapar; denetim düşerse durur) → o klasörde commit + push
(yazar `mail@5-levent.com`). README/LICENSE kaynağı `yayin/`. Kopyada Yönetim Planı PDF'i yok: `plan_ic.py` PDF yoksa
`kaynak/plan-meta.json` + hazır `plan-sNN` dosyalarıyla çalışır (kopyadan `uret.py` aynı `model.json`'u üretir, 24.10.2026'da denendi).

## Ekstra Bilgiler katmanları (24.10.2026; ilk adı "Gereksiz bilgiler")

Menü (seçim yokken, Blok seç'in yanında): otopark rengi · havuza süre (yalnız C3 zemin çıkışı) · çıkış kapısına uzaklık ·
A blok ticari yürüyüş · **güneş alma** · **manzara açıklığı** · arsa payı/brüt m² · bahçe-teras tahsisi.
Güneş ve manzara üreteçte hesaplanır (`gunes.py`, ~30 sn): cephe noktaları, blok + komşu bina gölgesi (arazi hariç), 52 hafta × 20 dk;
model.json `gunes.h` = 52 hafta × saat×10 (base64). Daire kartında haftalık güneş grafiği. "Otopark yerlerinin durumu" katmanı
24.10.2026'da kullanıcı onayıyla canlıya alındı.
