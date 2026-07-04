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
    """Gemini çağrısı; geçici sunucu yoğunluğunda (503/429) bekleyip yeniden dener."""
    son_hata = None
    for bekleme in (0, 30, 90):
        if bekleme:
            print(f"⏳ Gemini yoğun, {bekleme} sn bekleyip yeniden denenecek...")
            time.sleep(bekleme)
        try:
            return client.models.generate_content(model=model, contents=contents)
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


def oyunu_test_et(html_yolu, client, model):
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

        # --- TEST 1: Sayfa çökmeden açıldı mı? ---
        if hatalar:
            browser.close()
            return {"gecti": False, "puan": 0,
                    "yorum": "Oyun açılırken konsol hatası verdi.",
                    "sorunlar": [f"Konsol hatası: {h}" for h in hatalar[:3]],
                    "api_cagrisi": 0}

        ekranlar.append(page.screenshot())  # Menü ekranı

        # --- TEST 2: Oyun başlatılabiliyor mu? ---
        try:
            page.locator("#baslaBtn").click(timeout=3000)
        except Exception:
            # Buton bulunamazsa canvas ortasına tıklamayı dene
            try:
                page.locator("canvas").first.click(timeout=3000)
            except Exception:
                sorunlar.append("Başlat butonu (#baslaBtn) bulunamadı ve canvas tıklanamadı.")
        page.wait_for_timeout(1500)

        durum = _durum_oku(page)
        if durum is None:
            sorunlar.append("window.OYUN_DURUMU objesi yok; kural 11 uygulanmamış.")
        elif durum.get("asama") == "menu":
            sorunlar.append("Başlat'a tıklandı ama oyun 'menu' aşamasında kaldı.")

        # --- TEST 3: Pasif denge - hiç oynamadan can düşmeli ---
        baslangic_can = (durum or {}).get("can")
        page.wait_for_timeout(20000)
        durum = _durum_oku(page)
        if durum and baslangic_can is not None:
            if durum.get("can") == baslangic_can and durum.get("asama") == "oyunda":
                sorunlar.append("20 saniye hiç oynanmadığı halde can azalmadı: "
                                "düşmanlar gelmiyor veya oyun çok kolay.")

        # --- TEST 4: Aktif oynayış - canvas'a kule yerleştir, ilerlemeyi izle ---
        canvas = page.locator("canvas").first
        kutu = canvas.bounding_box()
        if kutu:
            for _ in range(12):  # Rastgele 12 noktaya kule yerleştirmeyi dene
                x = kutu["x"] + random.uniform(0.15, 0.85) * kutu["width"]
                y = kutu["y"] + random.uniform(0.15, 0.85) * kutu["height"]
                page.mouse.click(x, y)
                page.wait_for_timeout(400)

        page.wait_for_timeout(30000)  # ~30 sn oyunu izle
        ekranlar.append(page.screenshot())  # Oyun ortası ekranı

        durum = _durum_oku(page)
        if durum:
            if durum.get("asama") == "kaybetti" and durum.get("dalga", 99) <= 1:
                sorunlar.append("Bot kule yerleştirmesine rağmen daha 1. dalgada "
                                "kaybetti: oyun çok zor.")
            if durum.get("asama") == "kazandi":
                sorunlar.append("Oyun 1 dakikadan kısa sürede kazanıldı: çok kolay/kısa.")

        if hatalar:
            sorunlar.extend(f"Oyun sırasında konsol hatası: {h}" for h in hatalar[:3])

        browser.close()

    # --- TEST 5: Gemini görsel inceleme (sanal oyuncu yorumu) ---
    puan, yorum = 5, "Görsel inceleme yapılamadı."
    try:
        icerik = [types.Part.from_bytes(data=e, mime_type="image/png") for e in ekranlar]
        icerik.append(
            "Sen titiz bir oyun test kullanıcısısın. İlk görsel oyunun menüsü, "
            "ikincisi oyun ortası ekranı. Şunları değerlendir: yazılar Türkçe ve "
            "okunaklı mı, arayüz taşıyor/üst üste biniyor mu, oyun görsel olarak "
            "anlaşılır mı, ekranda gerçekten oyun oynanıyor gibi görünüyor mu? "
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
    kritik_var = any("konsol" in s.lower() or "çok zor" in s.lower()
                     or "can azalmadı" in s.lower() or "menu" in s.lower()
                     for s in sorunlar)
    gecti = (not kritik_var) and puan >= 6

    return {"gecti": gecti, "puan": puan, "yorum": yorum,
            "sorunlar": sorunlar, "api_cagrisi": api_cagrisi}
