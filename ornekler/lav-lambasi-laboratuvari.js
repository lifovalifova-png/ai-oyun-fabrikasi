const TEMA = {
  ad: "Lav Lambası Laboratuvarı",
  aciklama: "Kaçak lav damlaları laboratuvardan sızıyor: patlattığın her büyük damla küçüklere bölünür.",
  palet: { arka1:"#123a44", arka2:"#0b2930", yol:"#c9e8ee", yolKenar:"#2a1c33",
           dusman:"#ff4f6d", dusman2:"#ffa62b", kule:"#4dd0e1", mermi:"#fff3b0", vurgu:"#ffd166" },
  haritalar: [
    { ad: "Tezgâh Odası",
      yol: [{x:0,y:420},{x:230,y:420},{x:230,y:180},{x:560,y:180},{x:560,y:470},{x:900,y:470},{x:900,y:260},{x:1280,y:260}] },
    { ad: "Kazan Dairesi",
      palet: { arka1:"#3b2418", arka2:"#25150e", yol:"#f3d9c4", vurgu:"#ffb703" },
      yol: [{x:640,y:0},{x:640,y:150},{x:240,y:150},{x:240,y:400},{x:760,y:400},{x:1040,y:560},{x:1040,y:720}] },
    { ad: "Gözlem Kubbesi",
      palet: { arka1:"#1b1840", arka2:"#100d29", yol:"#e2dcff", vurgu:"#c77dff" },
      yol: [{x:1280,y:140},{x:980,y:140},{x:820,y:330},{x:980,y:520},{x:640,y:600},{x:300,y:520},{x:460,y:330},{x:300,y:140},{x:0,y:140}] }
  ],
  dusmanTipleri: [
    { ad:"Damlacık", can:40, hiz:92, altin:10, yaricap:11, renk:"#ff6b9d" },
    { ad:"Jöle", can:70, hiz:62, altin:12, yaricap:14, renk:"#ffa62b" },
    { ad:"Büyük Damla", can:140, hiz:46, altin:20, yaricap:18, renk:"#ff4f6d" },
    { ad:"Yapışkan", can:120, hiz:40, altin:18, yaricap:16, renk:"#58d68d", zirh:0.3 },
    { ad:"Ana Lav", can:260, hiz:36, altin:30, yaricap:20, renk:"#ff7b00" }
  ],
  kuleTipleri: [
    { ad:"Pipet Atıcı", fiyat:50, menzil:150, hasar:16, atisHizi:1.3, mermiHizi:380, renk:"#4dd0e1" },
    { ad:"Bunsen Ocağı", fiyat:90, menzil:120, hasar:40, atisHizi:0.55, mermiHizi:260, renk:"#ff7043", alan:50 },
    { ad:"Kriyo Şırınga", fiyat:70, menzil:135, hasar:9, atisHizi:0.95, mermiHizi:330, renk:"#90caf9", yavaslat:0.5 },
    { ad:"Tesla Bobini", fiyat:120, menzil:165, hasar:70, atisHizi:0.45, mermiHizi:420, renk:"#b388ff" }
  ],

  // ---------- yardımcı: renk tonu (aydınlık +, gölge −) ----------
  ton(hex, o) {
    const n = parseInt(hex.slice(1), 16);
    let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    if (o >= 0) { r += (255 - r) * o; g += (255 - g) * o; b += (255 - b) * o; }
    else { r *= 1 + o; g *= 1 + o; b *= 1 + o; }
    return "rgb(" + (r | 0) + "," + (g | 0) + "," + (b | 0) + ")";
  },

  arkaplanCiz(c, W, H, t, h) {
    const no = h ? h.no : 0, p = this.palet;
    // 1) zemin degradesi
    const g = c.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, this.ton(p.arka1, 0.08)); g.addColorStop(1, p.arka2);
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    // 2) karo dokusu (sol üst ışık: karonun sağ-alt kenarı koyu)
    for (let y = 0; y < H; y += 48) for (let x = (y / 48) % 2 ? 24 : 0; x < W; x += 48) {
      c.fillStyle = this.ton(p.arka1, 0.04); c.fillRect(x + 2, y + 2, 44, 44);
      c.fillStyle = this.ton(p.arka1, -0.25); c.fillRect(x + 2, y + 44, 44, 2); c.fillRect(x + 44, y + 2, 2, 44);
    }
    // 3) uzak dekor: raf + cam şişe siluetleri (soluk)
    c.globalAlpha = 0.35;
    for (let i = 0; i < 9; i++) {
      const x = 40 + i * 145, y = no === 2 ? 640 : 70;
      c.fillStyle = this.ton(p.arka2, -0.3); c.fillRect(x - 30, y + 26, 110, 8);
      c.fillStyle = this.ton(p.arka1, 0.25);
      c.beginPath(); c.moveTo(x, y + 26); c.lineTo(x + 6, y); c.lineTo(x + 14, y); c.lineTo(x + 20, y + 26); c.fill();
      c.beginPath(); c.arc(x + 48, y + 14, 12, 0, 6.29); c.fill();
    }
    c.globalAlpha = 1;
    // 4) orta mesafe: harita başına imza yapı
    if (no === 0) {               // tezgâh: büyük lav lambaları
      for (const [x, y, r] of [[110, 600, 1], [1180, 600, 1.2], [760, 90, 0.8]]) this.lamba(c, x, y, r, t);
    } else if (no === 1) {        // kazan dairesi: kazan + borular
      c.fillStyle = "#2a1c33";
      c.fillRect(0, 610, W, 14); c.fillRect(1180, 0, 14, H);
      this.kazan(c, 1120, 140); this.kazan(c, 120, 560);
    } else {                      // kubbe: yıldızlar + teleskop
      c.fillStyle = "#fff";
      for (let i = 0; i < 80; i++) { const x = (i * 197) % W, y = (i * 113) % 420; c.globalAlpha = 0.3 + (i % 5) / 8; c.fillRect(x, y, 2, 2); }
      c.globalAlpha = 1; this.lamba(c, 640, 330, 1.4, t);
    }
    // 5) korunan yapı: yolun sonundaki "Ana Reaktör" (hedef kale)
    const son = this.haritalar[no].yol[this.haritalar[no].yol.length - 1];
    const rx = Math.max(70, Math.min(W - 70, son.x)), ry = Math.max(90, Math.min(H - 90, son.y));
    c.fillStyle = "rgba(0,0,0,.35)"; c.beginPath(); c.ellipse(rx + 8, ry + 40, 52, 14, 0, 0, 6.29); c.fill();
    c.fillStyle = "#2a1c33"; c.beginPath(); c.arc(rx, ry, 44, 0, 6.29); c.fill();
    const rg = c.createRadialGradient(rx - 12, ry - 14, 4, rx, ry, 40);
    rg.addColorStop(0, "#fff7d6"); rg.addColorStop(0.4, p.vurgu); rg.addColorStop(1, this.ton(p.vurgu, -0.5));
    c.fillStyle = rg; c.beginPath(); c.arc(rx, ry, 38, 0, 6.29); c.fill();
  },

  lamba(c, x, y, s, t) {
    c.save(); c.translate(x, y); c.scale(s, s);
    c.fillStyle = "rgba(0,0,0,.35)"; c.beginPath(); c.ellipse(6, 34, 22, 6, 0, 0, 6.29); c.fill();
    c.fillStyle = "#2a1c33"; c.fillRect(-16, 22, 32, 12); c.fillRect(-10, -42, 20, 8);
    c.fillStyle = "#ffb3c7"; c.beginPath(); c.moveTo(-10, -34); c.lineTo(10, -34); c.lineTo(18, 22); c.lineTo(-18, 22); c.closePath(); c.fill();
    c.fillStyle = "#ff4f6d";
    c.beginPath(); c.arc(-3, 10, 9, 0, 6.29); c.arc(5, -12, 6, 0, 6.29); c.fill();
    c.strokeStyle = "#2a1c33"; c.lineWidth = 3;
    c.beginPath(); c.moveTo(-10, -34); c.lineTo(10, -34); c.lineTo(18, 22); c.lineTo(-18, 22); c.closePath(); c.stroke();
    c.fillStyle = "rgba(255,255,255,.55)"; c.fillRect(-7, -28, 3, 40);
    c.restore();
  },

  kazan(c, x, y) {
    c.fillStyle = "rgba(0,0,0,.35)"; c.beginPath(); c.ellipse(x + 8, y + 46, 50, 12, 0, 0, 6.29); c.fill();
    c.fillStyle = "#7a3b1d"; c.beginPath(); c.arc(x, y, 44, 0, 6.29); c.fill();
    c.fillStyle = "#b5602b"; c.beginPath(); c.arc(x - 8, y - 8, 30, 0, 6.29); c.fill();
    c.strokeStyle = "#2a1c33"; c.lineWidth = 3; c.beginPath(); c.arc(x, y, 44, 0, 6.29); c.stroke();
    c.fillStyle = "#ffb703"; c.fillRect(x - 12, y + 18, 24, 8);
  },

  yolCiz(c, yol, t, h) {
    const p = this.palet;
    c.lineCap = "round"; c.lineJoin = "round";
    const iz = () => { c.beginPath(); c.moveTo(yol[0].x, yol[0].y); for (let i = 1; i < yol.length; i++) c.lineTo(yol[i].x, yol[i].y); };
    c.save(); c.translate(6, 5); iz(); c.strokeStyle = "rgba(0,0,0,.35)"; c.lineWidth = 50; c.stroke(); c.restore();  // gölge
    iz(); c.strokeStyle = p.yolKenar; c.lineWidth = 50; c.stroke();                                             // kontur
    iz(); c.strokeStyle = this.ton(p.yol, -0.15); c.lineWidth = 42; c.stroke();                                // gölge tonu
    iz(); c.strokeStyle = p.yol; c.lineWidth = 34; c.stroke();                                                 // temel
    c.save(); c.translate(-3, -4); iz(); c.strokeStyle = this.ton(p.yol, 0.55); c.lineWidth = 6; c.stroke(); c.restore(); // cam parıltısı
    c.setLineDash([4, 26]); iz(); c.strokeStyle = this.ton(p.yolKenar, 0.25); c.lineWidth = 12; c.stroke(); c.setLineDash([]); // boru bileziği
  },

  dusmanCiz(c, d, t) {
    c.save(); c.translate(d.x, d.y);
    const r = d.yaricap, salla = Math.sin(t * 7 + d.faz) * 0.12;
    const temel = d.renk, ac = this.ton(temel, 0.45), kz = this.ton(temel, -0.45);
    // gölge (sağ alt)
    c.fillStyle = "rgba(0,0,0,.3)"; c.beginPath(); c.ellipse(r * 0.35, r * 0.85, r * 0.95, r * 0.32, 0, 0, 6.29); c.fill();
    // gövde: dalgalanan damla
    c.beginPath();
    for (let i = 0; i <= 14; i++) {
      const a = (i / 14) * 6.283, w = 1 + Math.sin(a * 3 + t * 5 + d.faz) * 0.08;
      const rx = r * (1 + salla) * w, ry = r * (1 - salla) * w;
      i ? c.lineTo(Math.cos(a) * rx, Math.sin(a) * ry - (a > 4 && a < 5.4 ? r * 0.25 : 0)) : c.moveTo(Math.cos(a) * rx, Math.sin(a) * ry);
    }
    c.closePath(); c.fillStyle = temel; c.fill();
    c.lineWidth = 2.5; c.strokeStyle = "#2a1c33"; c.stroke();
    // gölge tonu (sağ alt yarım ay) ve aydınlık (sol üst)
    c.fillStyle = kz; c.beginPath(); c.arc(r * 0.18, r * 0.2, r * 0.75, -0.2, 2.2); c.fill();
    c.fillStyle = ac; c.beginPath(); c.ellipse(-r * 0.35, -r * 0.4, r * 0.32, r * 0.2, -0.6, 0, 6.29); c.fill();
    // tipe göre detay (son dal koşulsuz else)
    if (d.tipIndeks === 0) {                 // Damlacık: tek iri göz
      c.fillStyle = "#fff"; c.beginPath(); c.arc(0, -r * 0.05, r * 0.38, 0, 6.29); c.fill();
      c.fillStyle = "#2a1c33"; c.beginPath(); c.arc(r * 0.08, 0, r * 0.18, 0, 6.29); c.fill();
    } else if (d.tipIndeks === 3) {          // Yapışkan: zırh kabarcıkları
      c.fillStyle = this.ton(temel, 0.25);
      for (let i = 0; i < 5; i++) { c.beginPath(); c.arc(Math.cos(i * 1.3) * r * 0.55, Math.sin(i * 1.3) * r * 0.55, r * 0.18, 0, 6.29); c.fill(); }
      c.fillStyle = "#2a1c33"; c.fillRect(-r * 0.35, -r * 0.1, r * 0.2, r * 0.12); c.fillRect(r * 0.15, -r * 0.1, r * 0.2, r * 0.12);
    } else if (d.tipIndeks === 4) {          // Ana Lav: taç + iç çekirdek
      c.fillStyle = "#fff3b0"; c.beginPath(); c.arc(0, r * 0.1, r * 0.35, 0, 6.29); c.fill();
      c.fillStyle = "#2a1c33";
      c.beginPath(); c.moveTo(-r * 0.5, -r * 0.8); c.lineTo(-r * 0.3, -r * 1.15); c.lineTo(0, -r * 0.85); c.lineTo(r * 0.3, -r * 1.15); c.lineTo(r * 0.5, -r * 0.8); c.fill();
      c.fillRect(-r * 0.45, -r * 0.25, r * 0.22, r * 0.14); c.fillRect(r * 0.23, -r * 0.25, r * 0.22, r * 0.14);
    } else {                                  // Jöle / Büyük Damla: iki göz + ağız
      c.fillStyle = "#fff";
      c.beginPath(); c.arc(-r * 0.3, -r * 0.15, r * 0.22, 0, 6.29); c.arc(r * 0.3, -r * 0.15, r * 0.22, 0, 6.29); c.fill();
      c.fillStyle = "#2a1c33";
      c.beginPath(); c.arc(-r * 0.25, -r * 0.12, r * 0.1, 0, 6.29); c.arc(r * 0.35, -r * 0.12, r * 0.1, 0, 6.29); c.fill();
      c.lineWidth = 2; c.beginPath(); c.arc(0, r * 0.25, r * 0.22, 0.2, 2.9); c.stroke();
    }
    // bölünmeden yeni çıkmış parça: kısa sersem halkası
    if (d.ozel && d.ozel.sersem > 0) {
      c.strokeStyle = "#fff3b0"; c.lineWidth = 2; c.setLineDash([3, 4]);
      c.beginPath(); c.arc(0, -r * 1.1, r * 0.45, 0, 6.29); c.stroke(); c.setLineDash([]);
    }
    c.restore();
  },

  kuleCiz(c, k, t) {
    c.save(); c.translate(k.x, k.y);
    const renk = k.tip.renk, ac = this.ton(renk, 0.45), kz = this.ton(renk, -0.45), kon = "#2a1c33";
    // taban gölgesi + taş kaide (3 ton)
    c.fillStyle = "rgba(0,0,0,.35)"; c.beginPath(); c.ellipse(5, 17, 22, 8, 0, 0, 6.29); c.fill();
    c.fillStyle = "#47545c"; c.beginPath(); c.ellipse(0, 12, 21, 9, 0, 0, 6.29); c.fill();
    c.fillStyle = "#6f8089"; c.beginPath(); c.ellipse(-2, 10, 17, 6, 0, 0, 6.29); c.fill();
    c.strokeStyle = kon; c.lineWidth = 2.5; c.beginPath(); c.ellipse(0, 12, 21, 9, 0, 0, 6.29); c.stroke();
    if (k.tipIndeks === 0) {              // Pipet Atıcı: ince uzun cam pipet (dikey siluet)
      c.fillStyle = kz; c.fillRect(-7, -22, 14, 32);
      c.fillStyle = renk; c.fillRect(-7, -22, 10, 32);
      c.fillStyle = ac; c.fillRect(-5, -20, 3, 26);
      c.strokeStyle = kon; c.strokeRect(-7, -22, 14, 32);
      c.fillStyle = "#ff6b9d"; c.beginPath(); c.arc(0, -26, 8, 0, 6.29); c.fill(); c.stroke();
      c.save(); c.translate(0, -8); c.rotate(k.aci);
      c.fillStyle = kon; c.fillRect(4, -3, 18, 6);
      c.restore();
    } else if (k.tipIndeks === 1) {       // Bunsen Ocağı: geniş alçak brülör (yatay siluet)
      c.fillStyle = kz; c.fillRect(-18, -6, 36, 14);
      c.fillStyle = renk; c.fillRect(-18, -6, 30, 12);
      c.fillStyle = ac; c.fillRect(-16, -4, 26, 3);
      c.strokeStyle = kon; c.strokeRect(-18, -6, 36, 14);
      c.fillStyle = "#555"; c.fillRect(-4, -16, 8, 10); c.strokeRect(-4, -16, 8, 10);
      c.fillStyle = "#ffd166"; c.beginPath(); c.moveTo(-6, -16); c.quadraticCurveTo(0, -34, 6, -16); c.fill();
      c.fillStyle = "#4dd0e1"; c.beginPath(); c.moveTo(-3, -16); c.quadraticCurveTo(0, -26, 3, -16); c.fill();
    } else if (k.tipIndeks === 2) {       // Kriyo Şırınga: yuvarlak tank + kristal (yuvarlak siluet)
      c.fillStyle = kz; c.beginPath(); c.arc(0, -6, 15, 0, 6.29); c.fill();
      c.fillStyle = renk; c.beginPath(); c.arc(-2, -8, 12, 0, 6.29); c.fill();
      c.fillStyle = ac; c.beginPath(); c.arc(-6, -12, 4, 0, 6.29); c.fill();
      c.strokeStyle = kon; c.beginPath(); c.arc(0, -6, 15, 0, 6.29); c.stroke();
      c.save(); c.translate(0, -6); c.rotate(k.aci);
      c.fillStyle = "#e3f2fd"; c.fillRect(10, -3, 18, 6); c.strokeRect(10, -3, 18, 6);
      c.fillStyle = kon; c.fillRect(28, -1, 6, 2);
      c.restore();
    } else {                               // Tesla Bobini: sivri, sarmallı (sivri siluet)
      c.fillStyle = kz; c.beginPath(); c.moveTo(-12, 8); c.lineTo(0, -28); c.lineTo(12, 8); c.closePath(); c.fill();
      c.fillStyle = renk; c.beginPath(); c.moveTo(-12, 8); c.lineTo(0, -28); c.lineTo(5, 8); c.closePath(); c.fill();
      c.strokeStyle = kon; c.beginPath(); c.moveTo(-12, 8); c.lineTo(0, -28); c.lineTo(12, 8); c.closePath(); c.stroke();
      c.strokeStyle = "#ffd166"; c.lineWidth = 2;
      for (let i = 0; i < 4; i++) { c.beginPath(); c.moveTo(-9 + i * 2, 2 - i * 8); c.lineTo(9 - i * 2, -2 - i * 8); c.stroke(); }
      c.fillStyle = "#fff3b0"; c.beginPath(); c.arc(0, -30, 5, 0, 6.29); c.fill();
    }
    // seviye parçaları: Sv2 bakır bilezik, Sv3 altın yıldız
    if (k.seviye >= 2) { c.fillStyle = "#c77d3a"; c.fillRect(-14, 4, 28, 4); c.strokeStyle = kon; c.lineWidth = 1.5; c.strokeRect(-14, 4, 28, 4); }
    if (k.seviye >= 3) {
      c.fillStyle = "#ffd166"; c.beginPath();
      for (let i = 0; i < 10; i++) { const a = -1.57 + i * 0.628, rr = i % 2 ? 3 : 7; c.lineTo(15 + Math.cos(a) * rr, -18 + Math.sin(a) * rr); }
      c.fill(); c.stroke();
    }
    c.restore();
  },

  mekanik: {
    ad: "Bölünme",
    aciklama: "Büyük Damla ölünce iki Jöle'ye, Ana Lav iki Büyük Damla'ya bölünür. Yeni parçalar 1 saniye sersem kalır: alan hasarlı Bunsen Ocağı tam bu an için.",
    dusmanDogdu(d, o) {
      d.ozel.sersem = 0;
    },
    dusmanGuncelle(d, dt, o) {
      if (d.ozel.sersem > 0) { d.ozel.sersem -= dt; d.hizCarpani = 0.25; }
    },
    dusmanOldu(d, o, kule) {
      let tip = -1, adet = 0, oran = 0.5;
      if (d.bos) { tip = 2; adet = 3; oran = 0.4; }
      else if (d.tipIndeks === 4) { tip = 2; adet = 2; oran = 0.35; }
      else if (d.tipIndeks === 2) { tip = 1; adet = 2; oran = 0.35; }
      if (tip < 0) return;
      for (let i = 0; i < adet; i++) {
        const y = o.dusmanEkle(tip, { mesafe: Math.max(0, d.mesafe - 8 - i * 14), rota: d.rota, canOrani: oran });
        if (y) y.ozel.sersem = 1.0;
      }
      o.parcacik(d.x, d.y, d.renk, 14);
    },
    ciz(c, o, t) {
      // sersem parçaların altında sıcak buhar halkası (dünya katmanı)
      for (const d of o.dusmanlar) {
        if (!d.ozel || !(d.ozel.sersem > 0)) continue;
        c.globalAlpha = Math.min(1, d.ozel.sersem) * 0.5; c.strokeStyle = "#fff3b0"; c.lineWidth = 3;
        c.beginPath(); c.arc(d.x, d.y, d.yaricap * 1.5 + (1 - d.ozel.sersem) * 10, 0, 6.29); c.stroke();
      }
      c.globalAlpha = 1;
    }
  }
};
// SON
