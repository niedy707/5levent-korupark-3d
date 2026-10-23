// Paylaşım önizleme görseli (WhatsApp/sosyal medya kartı): Genel görünüm, arayüz gizli → public/assets/site-3b/onizleme.jpg (1200×630)
// Önce yerel sunucu: python3 araclar/site-3b/sunucu.py   ·   sonra: node araclar/site-3b/onizleme.mjs
import { chromium } from '../../node_modules/playwright/index.mjs';
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=metal'] });
const p = await b.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await p.goto('http://127.0.0.1:3042/3d'); await p.waitForFunction(() => window.hazir, null, { timeout: 60000 });
await p.addStyleTag({ content: '#panel,#blokcu,#bakis,#hakkinda,#zoom,#pusula,#alt,#etiketler .yer{display:none!important}' });
await p.evaluate(() => { const K = KORUPARK3B; K.kam.hedef.copy(K.V3(-50, -30, 62)); K.kam.az = 30; K.kam.el = 36; K.kam.uz = 345; });
await p.evaluate(() => dispatchEvent(new Event("resize"))); await p.waitForTimeout(2500);
await p.screenshot({ path: new URL('../../public/assets/site-3b/onizleme.jpg', import.meta.url).pathname, type: 'jpeg', quality: 84 });
await b.close(); console.log('public/assets/site-3b/onizleme.jpg');
