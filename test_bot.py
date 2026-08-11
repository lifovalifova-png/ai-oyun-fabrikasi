# -*- coding: utf-8 -*-
"""
test_bot.py - Robot Oyuncu
Oyunu headless tarayıcıda gerçekten açar, oynar, ölçer ve Gemini'ye
ekran görüntüleriyle yorumlatır. main.py içindeki üretim döngüsünden çağrılır.

Döner: rapor sözlüğü
  {"gecti": bool, "puan": int, "yorum": str, "sorunlar": [str, ...], "api_cagrisi": int}
"""

import os
import json
import random
import re
import time

from playwright.sync_api import sync_playwright
from google.genai import types
from google.genai import errors as genai_errors


def gemini_cagir(client, model, contents):
    """Gemini çağrısı; geçici yoğunlukta (503/429) VEYA boş yanıtta bekleyip yeniden dener."""
    son_hata = None
    for bekleme in (0, 30, 90, 180):
        if bekleme:
            print(f"⏳ Gemini yanıt veremedi, {bekleme} sn bekleyip yeniden denenecek...")
            time.sleep(bekleme)
        try:
            cevap = client.models.generate_content(model=model, contents=contents)
            if cevap.text:  # Dolu yanıt geldiyse başarı
                return cevap
            son_hata = ValueError("Gemini boş yanıt döndürdü (yoğunluk/kesinti).")
        except (genai_errors.ServerError, genai_errors.ClientError) as e:
            kod = getattr(e, "status_code", None) or getattr(e, "code", None)
            if kod not in (429, 500, 503):
                raise  # Kalıcı hata (yanlış anahtar vb.) -> bekleme, direkt yüksel
            son_hata = e
    raise son_hata


def _durum_oku(page):
    try:
        return page.evaluate("window.OYUN_DURUMU || null")
    except Exception:
        return None


def oyunu_test_et(html_yolu, client, model, fikir=""):
    sorunlar = []
    hatalar = []
    ekranlar = []
    api_cagrisi = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.on("pageerror", lambda e: hatalar.append(str(e)))
        page.on("console",
                lambda m: hatalar.append(m.text) if m.type == "error" else None)

        page.goto("file://" + os.path.abspath(html_yolu))
        page.wait_for_timeout(2500)

        # Canvas hiç yoksa oyun yapısal olarak bozuk demektir
        if page.locator("canvas").count() == 0:
            browser.close()
            return {"gecti": False, "puan": 0,
                    "yorum": "Sayfada canvas bulunamadı, oyun yüklenmedi.",
                    "sorunlar": ["Canvas yok: üretilen HTML bozuk."],
                    "api_cagrisi": 0, "kapak_png": None}

        # --- TEST 1: Sayfa çökmeden açıldı mı? ---
        if hatalar:
            browser.close()
            return {"gecti": False, "puan": 0,
                    "yorum": "Oyun açılırken konsol hatası verdi.",
                    "sorunlar": [f"Konsol hatası: {h}" for h in hatalar[:3]],
                    "api_cagrisi": 0, "kapak_png": None}

        try:
            ekranlar.append(page.screenshot(timeout=15000, animations="disabled"))
        except Exception:
            pass  # Menü ekranı alınamadı, devam

        # --- TEST 2: Oyun başlatılabiliyor mu? ---
        baslatildi = False
        for secici in ["#baslaBtn", "button:has-text('Başla')",
                       "button:has-text('Baslat')", "button:has-text('Oyna')",
                       "button:has-text('BAŞLA')", "text=/başla|oyna|start/i"]:
            try:
                page.locator(secici).first.click(timeout=1200)
                baslatildi = True
                break
            except Exception:
                continue
        if not baslatildi:
            # Son çare: canvas'a tıkla (birçok oyun tıklamayla başlar)
            try:
                page.locator("canvas").first.click(timeout=2000)
                baslatildi = True
            except Exception:
                pass
        page.wait_for_timeout(1500)

        durum = _durum_oku(page)
        if durum is None:
            sorunlar.append("window.OYUN_DURUMU objesi yok; kural 11 uygulanmamış.")
        elif durum.get("asama") == "menu":
            # Menüde kaldıysa bir kez daha canvas'a tıklayıp tekrar dene
            try:
                page.locator("canvas").first.click(timeout=1500)
                page.wait_for_timeout(1500)
                durum = _durum_oku(page)
            except Exception:
                pass
            if durum and durum.get("asama") == "menu":
                sorunlar.append("Başlat'a tıklandı ama oyun 'menu' aşamasında kaldı.")

        # --- TEST 3: Pasif denge - önce kule kur, sonra düşman gelmesini bekle ---
        # Not: Birçok oyunda ilk saniyeler hazırlık; bu yüzden erken kule kurup
        # daha uzun bekliyoruz ki "düşman gelmiyor" yanlış alarmı azalsın.
        baslangic_can = (durum or {}).get("can")
        canvas0 = page.locator("canvas").first
        try:
            kutu0 = canvas0.bounding_box(timeout=5000)
        except Exception:
            kutu0 = None

        tiklanan_noktalar = []  # Aynı noktaya iki kez tıklayıp kazara kule menüsü açmayalım

        def _kule_menusu_kapat():
            """Kazara açılan kule detay panelini kapatır (gerçek oyuncunun yapacağı gibi)."""
            try:
                if page.locator("#kuleMenu").get_attribute("class") or "":
                    sinif = page.locator("#kuleMenu").get_attribute("class") or ""
                    if "gizli" not in sinif:
                        page.locator("#kmKapat").click(timeout=1000)
                        page.wait_for_timeout(200)
            except Exception:
                pass

        def _bos_nokta_bul(kutu, oran_min, oran_max, deneme=8):
            """Önceki tıklamalardan uzak yeni bir nokta üretir (üst üste kule menüsü açmasın)."""
            for _ in range(deneme):
                x = kutu["x"] + random.uniform(oran_min, oran_max) * kutu["width"]
                y = kutu["y"] + random.uniform(oran_min, oran_max) * kutu["height"]
                if all(((x-px)**2 + (y-py)**2) ** 0.5 > 55 for px, py in tiklanan_noktalar):
                    tiklanan_noktalar.append((x, y))
                    return x, y
            return None, None

        if kutu0:
            for _ in range(6):  # Erken birkaç kule kur
                x, y = _bos_nokta_bul(kutu0, 0.2, 0.8)
                if x is None:
                    continue
                page.mouse.click(x, y)
                page.wait_for_timeout(300)
                _kule_menusu_kapat()
        page.wait_for_timeout(30000)  # Düşman dalgasının gelmesi için daha uzun süre
        durum = _durum_oku(page)

        # --- TEST 4: Aktif oynayış - canvas'a kule yerleştir, ilerlemeyi izle ---
        canvas = page.locator("canvas").first
        try:
            kutu = canvas.bounding_box(timeout=5000)
        except Exception:
            kutu = None
        if kutu:
            for _ in range(12):  # Rastgele noktalara kule yerleştirmeyi dene
                x, y = _bos_nokta_bul(kutu, 0.15, 0.85)
                if x is None:
                    continue
                page.mouse.click(x, y)
                page.wait_for_timeout(400)
                _kule_menusu_kapat()

        # TEST 4b: Oyun sırasında canvas'ı kapatan menü/overlay kalmış mı?
        try:
            engel = page.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return null;
                const r = c.getBoundingClientRect();
                const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
                if (!el || el.tagName === 'CANVAS') return null;
                const s = getComputedStyle(el);
                if (s.pointerEvents === 'none' || s.visibility === 'hidden') return null;
                return (el.innerText || el.tagName).slice(0, 40);
            }""")
            if engel:
                sorunlar.append(f"Oyun sırasında canvas'ı kapatan panel açık kalmış: {engel}")
        except Exception:
            pass

        # TEST 4c: Tempo ölçümü - 3 saniyede dalga/skor sıçraması makul mü?
        tempo_once = _durum_oku(page) or {}
        page.wait_for_timeout(3000)
        tempo_sonra = _durum_oku(page) or {}
        try:
            dalga_farki = (tempo_sonra.get("dalga", 0) or 0) - (tempo_once.get("dalga", 0) or 0)
            if dalga_farki >= 3:
                sorunlar.append("Oyun aşırı hızlı: 3 saniyede 3+ dalga ilerledi.")
        except Exception:
            pass

        page.wait_for_timeout(27000)  # Toplam ~30 sn oyunu izle
        _kule_menusu_kapat()  # Ekran görüntüsü öncesi son güvenlik: açık kalan panel varsa kapat
        try:
            ekranlar.append(page.screenshot(timeout=15000, animations="disabled"))
        except Exception:
            pass  # Oyun ortası ekranı alınamadı, devam

        son_durum = _durum_oku(page)
        if son_durum:
            if son_durum.get("asama") == "kaybetti" and son_durum.get("dalga", 99) <= 1:
                sorunlar.append("Bot kule yerleştirmesine rağmen daha 1. dalgada "
                                "kaybetti: oyun çok zor.")
            if son_durum.get("asama") == "kazandi":
                sorunlar.append("Oyun 1 dakikadan kısa sürede kazanıldı: çok kolay/kısa.")
            # Akıllı hareketsizlik kontrolü: ~60 sn boyunca can, dalga ve skorun
            # ÜÇÜ DE hiç değişmediyse oyun gerçekten donmuş/boş demektir.
            if baslangic_can is not None and son_durum.get("asama") == "oyunda":
                degisti = (son_durum.get("can") != baslangic_can
                           or (durum or {}).get("dalga") != son_durum.get("dalga")
                           or (durum or {}).get("skor") != son_durum.get("skor"))
                if not degisti:
                    sorunlar.append("Oyun boyunca can, dalga ve skor hiç değişmedi: "
                                    "oyun ilerlemiyor.")

        if hatalar:
            sorunlar.extend(f"Oyun sırasında konsol hatası: {h}" for h in hatalar[:3])

        browser.close()

    # --- TEST 5: Gemini görsel inceleme (sanal oyuncu yorumu) ---
    puan, yorum = 5, "Görsel inceleme yapılamadı."
    try:
        icerik = [types.Part.from_bytes(data=e, mime_type="image/png") for e in ekranlar]
        icerik.append(
            "Sen titiz bir oyun test kullanıcısısın. İlk görsel oyunun menüsü, "
            "ikincisi oyun ortası ekranı olmalı. Oyunun konsepti şu: \"" + fikir + "\". "
            "Şunları değerlendir: (1) İkinci görselde GERÇEKTEN oynanan bir oyun mu var "
            "(kuleler, düşmanlar, yol) yoksa hala menü/boş ekran mı? Oyun ekranı yoksa "
            "puan EN FAZLA 4 olabilir. (2) Görseller konseptteki temayı yansıtıyor mu "
            "(korsan oyununda deniz/gemi, uzayda yıldız/metal gibi)? Tema hiç yansımıyorsa "
            "puan EN FAZLA 5 olabilir. (3) Yazılar Türkçe ve okunaklı mı, arayüz taşıyor mu? "
            "(4) İkinci görselde oyunun üzerini kapatan menü/başlangıç paneli hala duruyor mu? "
            "Duruyorsa bunu sorun olarak yaz ve puan EN FAZLA 4 olsun. "
            'SADECE şu JSON ile cevap ver, başka hiçbir şey yazma: '
            '{"puan": 1-10 arasi tam sayi, "yorum": "1-2 cümlelik Türkçe oyuncu yorumu", '
            '"sorunlar": ["varsa sorun listesi"]}'
        )
        cevap = gemini_cagir(client, model, icerik)
        api_cagrisi += 1
        metin = re.sub(r"^```json\s*|^```\s*|```$", "", cevap.text.strip(),
                       flags=re.MULTILINE).strip()
        veri = json.loads(metin)
        puan = int(veri.get("puan", 5))
        yorum = veri.get("yorum", "")
        sorunlar.extend(veri.get("sorunlar", []))
    except Exception as e:
        sorunlar.append(f"Görsel inceleme tamamlanamadı: {e}")

    # --- KARAR ---
    # Sadece GERÇEK bozukluklar kritik: konsol hatası, oyunun hiç ilerlememesi,
    # menüde takılıp kalma, 1. dalgada imkansızlık. "Görsel inceleme tamamlanamadı"
    # gibi geçici teknik aksaklıklar kritik sayılmaz.
    kritik_anahtarlar = ("konsol hatası", "ilerlemiyor", "menu' aşamasında",
                         "çok zor", "tıklanamadı", "panel açık kalmış",
                         "aşırı hızlı", "hala duruyor")
    kritik_var = any(any(a in s.lower() for a in kritik_anahtarlar) for s in sorunlar)
    gecti = (not kritik_var) and puan >= 6

    # Kapak resmi: zaten alınmış ekran görüntülerinden — ek API çağrısı YOK, ek maliyet YOK.
    # Oyun ortası ekranı (varsa) menüden daha çekici olduğu için tercih edilir.
    kapak_png = ekranlar[-1] if len(ekranlar) >= 2 else (ekranlar[0] if ekranlar else None)

    return {"gecti": gecti, "puan": puan, "yorum": yorum,
            "sorunlar": sorunlar, "api_cagrisi": api_cagrisi, "kapak_png": kapak_png}
