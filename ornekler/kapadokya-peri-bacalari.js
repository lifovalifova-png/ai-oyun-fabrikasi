const TEMA = {
  ad: "Kapadokya Peri Bacaları",
  aciklama: "Akıncılar vadinin tüf tünellerinden süzülüyor: tünelde göremediğini vuramazsın, kandil gözcüsü yolunu aydınlatsın.",
  palet: { arka1:"#e9b98f", arka2:"#c98d66", yol:"#f6dcc0", yolKenar:"#3a2418",
           dusman:"#5b2c83", dusman2:"#2e6f8e", kule:"#f2c14e", mermi:"#fff1c1", vurgu:"#f2c14e" },
  haritalar: [
    { ad: "Göreme Vadisi",
      yol: [{x:0,y:200},{x:340,y:200},{x:340,y:470},{x:700,y:470},{x:700,y:250},{x:1020,y:250},{x:1020,y:520},{x:1280,y:520}] },
    { ad: "Uçhisar Eteği",
      palet: { arka1:"#d9a27c", arka2:"#a8694a", yol:"#f1d2b4" },
      yol: [{x:1280,y:380},{x:1000,y:380},{x:860,y:180},{x:560,y:180},{x:420,y:420},{x:700,y:560},{x:260,y:600},{x:120,y:330},{x:0,y:330}] },
    { ad: "Derinkuyu Yeraltı Şehri",
      palet: { arka1:"#5a3d33", arka2:"#2b1c18", yol:"#d8b89a", yolKenar:"#140c09" },
      yol: [{x:640,y:0},{x:640,y:130},{x:240,y:130},{x:240,y:330},{x:1040,y:330},{x:1040,y:540},{x:420,y:540},{x:420,y:720}] }
  ],
  dusmanTipleri: [
    { ad:"Kertenkele", can:45, hiz:90, altin:10, yaricap:12, renk:"#3f8f5a" },
    { ad:"Akıncı", can:70, hiz:64, altin:12, yaricap:14, renk:"#5b2c83" },
    { ad:"Köstebek Madenci", can:95, hiz:50, altin:16, yaricap:15, renk:"#2e6f8e" },
    { ad:"Tüf Golemi", can:170, hiz:40, altin:22, yaricap:18, renk:"#7a7f8c", zirh:0.3 },
    { ad:"Yer Ejderi", can:260, hiz:38, altin:30, yaricap:20, renk:"#a33b2c" }
  ],
  kuleTipleri: [
    { ad:"Baca Okçusu", fiyat:55, menzil:150, hasar:17, atisHizi:1.2, mermiHizi:380, renk:"#f2c14e" },
    { ad:"Kaya Mancınığı", fiyat:95, menzil:125, hasar:44, atisHizi:0.5, mermiHizi:250, renk:"#c2703d", alan:52 },
    { ad:"Testi Atıcı", fiyat:70, menzil:135, hasar:9, atisHizi:0.9, mermiHizi:320, renk:"#3d8fb5", yavaslat:0.5 },
    { ad:"Kandil Gözcüsü", fiyat:65, menzil:120, hasar:7, atisHizi:1.0, mermiHizi:340, renk:"#ffd36b" }
  ],

  // tünel aralıkları (yol uzunluğunun oranı), harita başına
  tuneller: [
    [[0.22, 0.34], [0.60, 0.70]],
    [[0.16, 0.28], [0.44, 0.54], [0.74, 0.84]],
    [[0.10, 0.24], [0.36, 0.48], [0.58, 0.70], [0.80, 0.90]]
  ],

  ton(hex, o) {
    const n = parseInt(hex.slice(1), 16);
    let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    if (o >= 0) { r += (255 - r) * o; g += (255 - g) * o; b += (255 - b) * o; }
    else { r *= 1 + o; g *= 1 + o; b *= 1 + o; }
    return "rgb(" + (r | 0) + "," + (g | 0) + "," + (b | 0) + ")";
  },

  baca(c, x, y, s, renk) {           // peri bacası: koni gövde + şapka taşı, sol üst ışık
    c.save(); c.translate(x, y); c.scale(s, s);
    c.fillStyle = "rgba(0,0,0,.25)"; c.beginPath(); c.ellipse(14, 2, 34, 9, 0, 0, 6.29); c.fill();
    c.fillStyle = this.ton(renk, -0.3); c.beginPath(); c.moveTo(-26, 0); c.quadraticCurveTo(-8, -70, -6, -96); c.lineTo(6, -96); c.quadraticCurveTo(10, -70, 26, 0); c.fill();
    c.fillStyle = renk; c.beginPath(); c.moveTo(-26, 0); c.quadraticCurveTo(-8, -70, -6, -96); c.lineTo(2, -96); c.quadraticCurveTo(0, -60, 6, 0); c.fill();
    c.fillStyle = this.ton(renk, 0.35); c.fillRect(-14, -50, 4, 34);
    c.fillStyle = "#6b4a3a"; c.beginPath(); c.ellipse(0, -100, 16, 9, 0, 0, 6.29); c.fill();
    c.fillStyle = "#3a2418"; c.fillRect(-4, -40, 8, 12);                 // oyma pencere
    c.strokeStyle = "#3a2418"; c.lineWidth = 2;
    c.beginPath(); c.moveTo(-26, 0); c.quadraticCurveTo(-8, -70, -6, -96); c.lineTo(6, -96); c.quadraticCurveTo(10, -70, 26, 0); c.stroke();
    c.restore();
  },

  arkaplanCiz(c, W, H, t, h) {
    const no = h ? h.no : 0, p = this.palet;
    const g = c.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, this.ton(p.arka1, 0.12)); g.addColorStop(1, p.arka2);
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    if (no < 2) {
      // uzak sıradağ silueti
      c.fillStyle = this.ton(p.arka1, 0.3); c.globalAlpha = 0.6;
      c.beginPath(); c.moveTo(0, 150);
      for (let x = 0; x <= W; x += 80) c.lineTo(x, 110 + Math.sin(x * 0.013) * 30 + Math.sin(x * 0.041) * 12);
      c.lineTo(W, 0); c.lineTo(0, 0); c.fill(); c.globalAlpha = 1;
      // zemin dokusu: tüf çatlakları
      c.strokeStyle = this.ton(p.arka2, -0.15); c.lineWidth = 1.5;
      for (let i = 0; i < 60; i++) { const x = (i * 211) % W, y = 160 + (i * 97) % (H - 170);
        c.beginPath(); c.moveTo(x, y); c.lineTo(x + 18, y + 6); c.lineTo(x + 30, y + 2); c.stroke(); }
      // peri bacaları (orta mesafe)
      const bacalar = no === 0 ? [[90, 640, 1], [160, 120, 0.7], [1180, 160, 0.9], [860, 690, 0.8], [520, 330, 0.6]]
                               : [[1180, 680, 1], [80, 140, 0.8], [700, 360, 0.7], [1150, 140, 0.7]];
      for (const [x, y, s] of bacalar) this.baca(c, x, y, s, p.arka1);
      if (no === 1) {               // Uçhisar kaya kalesi
        c.fillStyle = this.ton(p.arka2, -0.2);
        c.beginPath(); c.moveTo(980, 120); c.quadraticCurveTo(1040, 10, 1120, 40); c.quadraticCurveTo(1200, 70, 1240, 130); c.fill();
        c.fillStyle = "#3a2418"; for (let i = 0; i < 6; i++) c.fillRect(1020 + i * 30, 70 + (i % 2) * 18, 9, 12);
      }
    } else {
      // yeraltı şehri: oyma odalar ve havalandırma bacası ışığı
      c.fillStyle = "rgba(0,0,0,.35)";
      for (let i = 0; i < 14; i++) { const x = 60 + (i * 173) % 1160, y = 60 + (i * 89) % 600;
        c.beginPath(); c.ellipse(x, y, 40, 26, 0, Math.PI, 0); c.lineTo(x + 40, y + 20); c.lineTo(x - 40, y + 20); c.fill(); }
      const lg = c.createRadialGradient(840, 140, 10, 840, 140, 220);
      lg.addColorStop(0, "rgba(255,225,170,.35)"); lg.addColorStop(1, "rgba(255,225,170,0)");
      c.fillStyle = lg; c.fillRect(600, 0, 480, 400);
      c.fillStyle = "#8a6a55"; c.beginPath(); c.arc(110, 640, 40, 0, 6.29); c.fill();       // sürgü taşı kapı
      c.strokeStyle = "#140c09"; c.lineWidth = 3; c.stroke(); c.beginPath(); c.arc(110, 640, 8, 0, 6.29); c.stroke();
    }
    // korunan yapı: kervansaray kapısı (yolun sonu)
    const yl = this.haritalar[no].yol, son = yl[yl.length - 1];
    const x = Math.max(70, Math.min(W - 70, son.x)), y = Math.max(80, Math.min(H - 80, son.y));
    c.fillStyle = "rgba(0,0,0,.3)"; c.fillRect(x - 46, y + 30, 100, 10);
    c.fillStyle = "#b07a55"; c.fillRect(x - 50, y - 40, 100, 74);
    c.fillStyle = "#d6a27c"; c.fillRect(x - 50, y - 40, 100, 10);
    c.fillStyle = "#3a2418"; c.beginPath(); c.moveTo(x - 18, y + 34); c.lineTo(x - 18, y - 6); c.quadraticCurveTo(x, y - 26, x + 18, y - 6); c.lineTo(x + 18, y + 34); c.fill();
    c.strokeStyle = "#3a2418"; c.lineWidth = 3; c.strokeRect(x - 50, y - 40, 100, 74);
  },

  yolCiz(c, yol, t, h) {
    const p = this.palet;
    c.lineCap = "round"; c.lineJoin = "round";
    const iz = () => { c.beginPath(); c.moveTo(yol[0].x, yol[0].y); for (let i = 1; i < yol.length; i++) c.lineTo(yol[i].x, yol[i].y); };
    c.save(); c.translate(5, 4); iz(); c.strokeStyle = "rgba(0,0,0,.3)"; c.lineWidth = 48; c.stroke(); c.restore();
    iz(); c.strokeStyle = p.yolKenar; c.lineWidth = 48; c.stroke();
    iz(); c.strokeStyle = this.ton(p.yol, -0.18); c.lineWidth = 40; c.stroke();
    iz(); c.strokeStyle = p.yol; c.lineWidth = 32; c.stroke();
    c.setLineDash([2, 18]); iz(); c.strokeStyle = this.ton(p.yol, -0.3); c.lineWidth = 6; c.stroke(); c.setLineDash([]);
  },

  dusmanCiz(c, d, t) {
    c.save(); c.translate(d.x, d.y);
    const r = d.yaricap, adim = Math.sin(t * 9 + d.faz), temel = d.renk;
    const ac = this.ton(temel, 0.4), kz = this.ton(temel, -0.45), kon = "#24140d";
    c.fillStyle = "rgba(0,0,0,.3)"; c.beginPath(); c.ellipse(r * 0.3, r * 0.9, r * 0.9, r * 0.3, 0, 0, 6.29); c.fill();
    if (d.tipIndeks === 0) {                    // Kertenkele: yassı gövde + kuyruk
      c.rotate(d.aci || 0);
      c.fillStyle = kz; c.beginPath(); c.moveTo(-r * 1.6, Math.sin(t * 9 + d.faz) * 3); c.lineTo(-r * 0.5, -r * 0.3); c.lineTo(-r * 0.5, r * 0.3); c.fill();
      c.fillStyle = temel; c.beginPath(); c.ellipse(0, 0, r, r * 0.55, 0, 0, 6.29); c.fill();
      c.strokeStyle = kon; c.lineWidth = 2; c.stroke();
      c.fillStyle = ac; c.beginPath(); c.ellipse(-r * 0.2, -r * 0.2, r * 0.5, r * 0.18, 0, 0, 6.29); c.fill();
      c.fillStyle = kon; c.fillRect(-r * 0.3, -r * 0.75 + adim * 2, 3, r * 0.35); c.fillRect(r * 0.2, r * 0.45 - adim * 2, 3, r * 0.35);
      c.fillStyle = "#fff"; c.beginPath(); c.arc(r * 0.7, -r * 0.15, r * 0.16, 0, 6.29); c.fill();
    } else if (d.tipIndeks === 2) {              // Köstebek Madenci: yuvarlak + kask feneri + kazma
      c.fillStyle = temel; c.beginPath(); c.arc(0, 0, r, 0, 6.29); c.fill();
      c.strokeStyle = kon; c.lineWidth = 2.5; c.stroke();
      c.fillStyle = kz; c.beginPath(); c.arc(r * 0.15, r * 0.2, r * 0.7, -0.3, 2.3); c.fill();
      c.fillStyle = "#f2c14e"; c.beginPath(); c.arc(0, -r * 0.55, r * 0.6, Math.PI, 0); c.fill(); c.stroke();
      c.fillStyle = "#fff6c9"; c.beginPath(); c.arc(0, -r * 0.75, r * 0.18, 0, 6.29); c.fill();
      c.fillStyle = "#f7b6c2"; c.beginPath(); c.arc(r * 0.55, r * 0.05, r * 0.2, 0, 6.29); c.fill();
      c.save(); c.rotate(-0.6 + adim * 0.3); c.fillStyle = "#6b4a3a"; c.fillRect(r * 0.6, -r * 0.1, r * 0.9, 3);
      c.fillStyle = "#c9ced6"; c.fillRect(r * 1.4, -r * 0.45, 4, r * 0.9); c.restore();
    } else if (d.tipIndeks === 3) {              // Tüf Golemi: köşeli taş bloklar
      c.fillStyle = kz; c.fillRect(-r * 0.9, -r * 0.7, r * 1.8, r * 1.6);
      c.fillStyle = temel; c.fillRect(-r * 0.9, -r * 0.7, r * 1.5, r * 1.3);
      c.fillStyle = ac; c.fillRect(-r * 0.8, -r * 0.6, r * 0.6, r * 0.3);
      c.strokeStyle = kon; c.lineWidth = 2.5; c.strokeRect(-r * 0.9, -r * 0.7, r * 1.8, r * 1.6);
      c.fillStyle = "#ffcf5a"; c.fillRect(-r * 0.45, -r * 0.25, r * 0.25, r * 0.18); c.fillRect(r * 0.2, -r * 0.25, r * 0.25, r * 0.18);
      c.fillStyle = kz; c.fillRect(-r * 1.25, -r * 0.2 + adim * 2, r * 0.35, r * 0.7); c.fillRect(r * 0.9, -r * 0.2 - adim * 2, r * 0.35, r * 0.7);
    } else if (d.tipIndeks === 4) {              // Yer Ejderi: uzun gövde, sırt dikenleri
      c.rotate(d.aci || 0);
      for (let i = 3; i >= 0; i--) {
        const x = -i * r * 0.6, y = Math.sin(t * 6 + d.faz + i) * 3;
        c.fillStyle = i % 2 ? kz : temel; c.beginPath(); c.arc(x, y, r * (0.85 - i * 0.1), 0, 6.29); c.fill();
        c.strokeStyle = kon; c.lineWidth = 2; c.stroke();
        c.fillStyle = "#f2c14e"; c.beginPath(); c.moveTo(x - 4, y - r * 0.7); c.lineTo(x, y - r * 1.1); c.lineTo(x + 4, y - r * 0.7); c.fill();
      }
      c.fillStyle = "#fff"; c.beginPath(); c.arc(r * 0.35, -r * 0.25, r * 0.17, 0, 6.29); c.fill();
      c.fillStyle = kon; c.beginPath(); c.arc(r * 0.4, -r * 0.25, r * 0.08, 0, 6.29); c.fill();
    } else {                                      // Akıncı: başlıklı, pelerinli insan
      c.fillStyle = kz; c.beginPath(); c.moveTo(-r * 0.8, r * 0.9); c.lineTo(0, -r * 0.4); c.lineTo(r * 0.8, r * 0.9); c.fill();
      c.fillStyle = temel; c.beginPath(); c.moveTo(-r * 0.8, r * 0.9); c.lineTo(0, -r * 0.4); c.lineTo(r * 0.3, r * 0.9); c.fill();
      c.strokeStyle = kon; c.lineWidth = 2; c.beginPath(); c.moveTo(-r * 0.8, r * 0.9); c.lineTo(0, -r * 0.4); c.lineTo(r * 0.8, r * 0.9); c.closePath(); c.stroke();
      c.fillStyle = "#e8b48a"; c.beginPath(); c.arc(0, -r * 0.55, r * 0.4, 0, 6.29); c.fill(); c.stroke();
      c.fillStyle = "#f2f2f2"; c.beginPath(); c.arc(0, -r * 0.75, r * 0.42, Math.PI, 0); c.fill(); c.stroke();
      c.fillStyle = "#c9ced6"; c.fillRect(r * 0.6, -r * 0.6 + adim * 2, 3, r * 1.2);
    }
    c.restore();
  },

  kuleCiz(c, k, t) {
    c.save(); c.translate(k.x, k.y);
    const renk = k.tip.renk, ac = this.ton(renk, 0.45), kz = this.ton(renk, -0.45), kon = "#24140d";
    c.fillStyle = "rgba(0,0,0,.3)"; c.beginPath(); c.ellipse(6, 16, 22, 8, 0, 0, 6.29); c.fill();
    c.fillStyle = "#8a6a55"; c.beginPath(); c.ellipse(0, 12, 20, 8, 0, 0, 6.29); c.fill();
    c.fillStyle = "#b08d75"; c.beginPath(); c.ellipse(-2, 10, 15, 5, 0, 0, 6.29); c.fill();
    c.strokeStyle = kon; c.lineWidth = 2.5; c.beginPath(); c.ellipse(0, 12, 20, 8, 0, 0, 6.29); c.stroke();
    if (k.tipIndeks === 0) {                 // Baca Okçusu: minyatür peri bacası (dikey)
      c.fillStyle = kz; c.beginPath(); c.moveTo(-12, 10); c.quadraticCurveTo(-4, -18, -4, -26); c.lineTo(4, -26); c.quadraticCurveTo(4, -18, 12, 10); c.fill();
      c.fillStyle = "#e9b98f"; c.beginPath(); c.moveTo(-12, 10); c.quadraticCurveTo(-4, -18, -4, -26); c.lineTo(1, -26); c.quadraticCurveTo(0, -10, 4, 10); c.fill();
      c.strokeStyle = kon; c.beginPath(); c.moveTo(-12, 10); c.quadraticCurveTo(-4, -18, -4, -26); c.lineTo(4, -26); c.quadraticCurveTo(4, -18, 12, 10); c.stroke();
      c.fillStyle = "#6b4a3a"; c.beginPath(); c.ellipse(0, -28, 9, 5, 0, 0, 6.29); c.fill(); c.stroke();
      c.save(); c.translate(0, -10); c.rotate(k.aci);
      c.strokeStyle = kon; c.lineWidth = 2; c.beginPath(); c.arc(6, 0, 9, -1.2, 1.2); c.stroke();
      c.fillStyle = renk; c.fillRect(4, -1, 16, 2); c.restore();
    } else if (k.tipIndeks === 1) {          // Kaya Mancınığı: geniş ahşap gövde (yatay)
      c.fillStyle = "#7a4a2e"; c.fillRect(-18, -4, 36, 10); c.strokeStyle = kon; c.strokeRect(-18, -4, 36, 10);
      c.fillStyle = "#a8683f"; c.fillRect(-16, -2, 32, 3);
      c.save(); c.rotate(k.aci); c.fillStyle = "#5b3620"; c.fillRect(-4, -3, 26, 6); c.strokeRect(-4, -3, 26, 6);
      c.fillStyle = renk; c.beginPath(); c.arc(24, 0, 6, 0, 6.29); c.fill(); c.stroke(); c.restore();
      c.fillStyle = "#3a2418"; c.beginPath(); c.arc(-12, 7, 5, 0, 6.29); c.arc(12, 7, 5, 0, 6.29); c.fill();
    } else if (k.tipIndeks === 2) {          // Testi Atıcı: Avanos çömleği (yuvarlak)
      c.fillStyle = kz; c.beginPath(); c.arc(0, -6, 15, 0, 6.29); c.fill();
      c.fillStyle = "#c2703d"; c.beginPath(); c.arc(-2, -8, 12, 0, 6.29); c.fill();
      c.fillStyle = "#e39b67"; c.beginPath(); c.arc(-6, -12, 4, 0, 6.29); c.fill();
      c.strokeStyle = kon; c.beginPath(); c.arc(0, -6, 15, 0, 6.29); c.stroke();
      c.strokeStyle = renk; c.lineWidth = 3; c.beginPath(); c.arc(0, -6, 10, 0.4, 2.7); c.stroke();
      c.save(); c.translate(0, -18); c.rotate(k.aci); c.fillStyle = "#c2703d"; c.fillRect(0, -4, 14, 8);
      c.strokeStyle = kon; c.lineWidth = 2; c.strokeRect(0, -4, 14, 8); c.restore();
    } else {                                   // Kandil Gözcüsü: sivri direk + yanan kandil
      c.fillStyle = "#5b3620"; c.fillRect(-3, -26, 6, 34); c.strokeStyle = kon; c.strokeRect(-3, -26, 6, 34);
      c.fillStyle = kz; c.beginPath(); c.moveTo(-9, -26); c.lineTo(0, -38); c.lineTo(9, -26); c.fill(); c.stroke();
      c.fillStyle = renk; c.beginPath(); c.arc(0, -22, 7, 0, 6.29); c.fill(); c.stroke();
      c.fillStyle = "#fff6c9"; c.beginPath(); c.arc(-2, -24, 3, 0, 6.29); c.fill();
    }
    if (k.seviye >= 2) { c.fillStyle = "#3d8fb5"; c.fillRect(-14, 4, 28, 4); c.strokeStyle = kon; c.lineWidth = 1.5; c.strokeRect(-14, 4, 28, 4); }
    if (k.seviye >= 3) { c.fillStyle = "#f2c14e"; c.beginPath(); c.moveTo(12, -30); c.lineTo(22, -26); c.lineTo(12, -22); c.fill(); c.fillRect(11, -32, 2, 22); }
    c.restore();
  },

  mekanik: {
    ad: "Tüneller",
    aciklama: "Düşmanlar tüf tünellerinden geçerken görünmez ve vurulamaz. Kandil Gözcüsü 120 px içindeki tünel kısmını aydınlatır. Köstebek Madenci tünelde %40 hızlanır.",
    basla(o) { o.bellek.parcalar = {}; },
    tunelde(d, o) {
      const ar = (this._tuneller || [])[o.harita] || [];
      const oran = d.mesafe / o.yolUzunlugu(d.rota);
      for (const a of ar) if (oran >= a[0] && oran <= a[1]) return true;
      return false;
    },
    dusmanGuncelle(d, dt, o) {
      if (!this.tunelde(d, o)) return;
      if (d.tipIndeks === 2) d.hizCarpani = 1.4;
      for (const k of o.yakinKuleler(d.x, d.y, 120)) if (k.tipIndeks === 3) return;   // kandil aydınlatıyor
      d.hedeflenebilir = false;
    },
    ciz(c, o, t) {
      // tünel ağızları: yolun üstüne taş kemer (içindeki düşman yarı görünür kalır)
      const ar = (this._tuneller || [])[o.harita] || [];
      for (const a of ar) {
        c.lineCap = "round"; c.lineWidth = 54; c.strokeStyle = "rgba(58,36,24,.62)";
        c.beginPath();
        for (let s = a[0]; s <= a[1] + 1e-6; s += 0.01) { const p = o.yolNoktasi(Math.min(s, a[1])); s === a[0] ? c.moveTo(p.x, p.y) : c.lineTo(p.x, p.y); }
        c.stroke();
        for (const u of [a[0], a[1]]) {
          const p = o.yolNoktasi(u);
          c.fillStyle = "#b07a55"; c.beginPath(); c.arc(p.x, p.y, 30, Math.PI, 0); c.fill();
          c.fillStyle = "#24140d"; c.beginPath(); c.arc(p.x, p.y + 2, 20, Math.PI, 0); c.fill();
        }
      }
      // kandil ışık halkaları
      for (const k of o.kuleler) if (k.tipIndeks === 3) {
        c.globalAlpha = 0.18 + Math.sin(t * 3 + k.x) * 0.04; c.fillStyle = "#ffd36b";
        c.beginPath(); c.arc(k.x, k.y, 120, 0, 6.29); c.fill(); c.globalAlpha = 1;
      }
    }
  }
};
TEMA.mekanik._tuneller = TEMA.tuneller;
// SON
