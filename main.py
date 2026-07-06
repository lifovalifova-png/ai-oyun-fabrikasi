# -*- coding: utf-8 -*-
"""
AI OYUN FABRİKASI - main.py
Günde 1 kez çalışır: Sheets'teki fikir havuzundan fikir alır,
Gemini ile oyun üretir, test eder, GitHub'a push eder, loglar.

Gerekli ortam değişkenleri:
  GEMINI_API_KEY : Google AI Studio API anahtarı
  GITHUB_PAT     : GitHub Personal Access Token
Gerekli dosya:
  credentials.json : Google Hizmet Hesabı anahtarı (Actions'ta base64'ten üretilir)
"""

import os
import re
import json
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from github import Github, Auth
from github.GithubException import GithubException
from google import genai

from test_bot import oyunu_test_et, gemini_cagir

# ================== AYARLAR ==================
SHEET_ADI = "AI Uygulama Fabrikası"   # Google Sheets dosya adı
LOG_SEKMESI = "Loglar"                # Log sekmesi (A:Tarih B:Oyun C:API D:Durum E:Not)
HAVUZ_SEKMESI = "FikirHavuzu"         # Fikir havuzu (A:Fikir B:Durum)
REPO_ADI = "ai-oyun-fabrikasi"        # GitHub repo adı
MODEL = "gemini-2.5-flash"
MAX_DENEME = 3
ANALYTICS_ID = "G-XXXXXXXXXX"         # Google Analytics 4 Ölçüm Kimliği (kurulumda değiştir)


# ================== YARDIMCILAR ==================
def slugify(text):
    text = text.lower().strip()
    for k, h in {'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c'}.items():
        text = text.replace(k, h)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:60]


def fikirden_baslik(fikir):
    """Fikrin ';' öncesindeki tema kısmını oyun adı yapar (kırpık kelime olmaz)."""
    baslik = fikir.split(";")[0].strip().rstrip(".,")
    return baslik[:60]


def analytics_ekle(html):
    """Sayfaya Google Analytics 4 kodunu enjekte eder (Gemini'ye güvenmeden)."""
    if ANALYTICS_ID.startswith("G-X"):  # Kimlik henüz girilmemişse dokunma
        return html
    snippet = f"""<script async src="https://www.googletagmanager.com/gtag/js?id={ANALYTICS_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{ANALYTICS_ID}');</script>
"""
    if "</head>" in html:
        return html.replace("</head>", snippet + "</head>", 1)
    return html  # </head> yoksa (beklenmez) dosyayı bozma


# ================== FİKİR HAVUZU ==================
def havuzdan_fikir_al(havuz):
    """B sütunu boş olan ilk fikri alır ve KULLANILDI işaretler."""
    satirlar = havuz.get_all_values()
    for i, satir in enumerate(satirlar, start=1):
        fikir = satir[0].strip() if len(satir) > 0 else ""
        durum = satir[1].strip() if len(satir) > 1 else ""
        if fikir and durum == "":
            havuz.update_cell(i, 2, "KULLANILDI")
            return fikir
    return None


# ================== ÜRETİM + KALİTE KONTROL ==================
KOD_KURALLARI = """
STRATEJİK VE KRİTİK KURALLAR:
1. TEKNOLOJİ: Sadece HTML5 <canvas>, saf JavaScript (ES6) ve arayüz/menüler için Tailwind CSS (CDN) kullan. Dış kütüphane YOK.
2. GRAFİKLER: Görsel/ses dosyası KULLANILMAYACAK. Emoji KULLANILMAYACAK. Her şey canvas üzerinde çizilecek.
3. OYUN DERİNLİĞİ: Başlangıç/Menü ekranı, EN AZ 8 düşman dalgası (artan zorluk, her 4. dalga güçlü BOSS düşmanı), en az 3 FARKLI kule tipi (farklı fiyat/menzil/hız), kuleye tıklayınca YÜKSELTME (2 seviye) ve SATMA seçeneği, Can/Skor/Altın göstergesi, dalga arası 5 saniyelik hazırlık süresi, oyun sonu ekranı ve "Yeniden Başlat" butonu.
4. KONTROLLER: Hem fare hem mobil dokunmatik (touch) desteklenecek. Kule seçimi için alt kısımda tıklanabilir panel olacak.
5. PERFORMANS: requestAnimationFrame + deltaTime kullan. Ekran dışına çıkan mermiler ve ölen düşmanlar diziden silinecek.
6. KOORDİNAT: Tıklama/dokunma konumları canvas.getBoundingClientRect() ile canvas'ın gerçek boyutuna oranlanacak. Canvas responsive olacak.
7. DİL: Tüm oyun içi metinler Türkçe olacak.
8. GÖRSEL KİMLİK (ÇOK ÖNEMLİ - basit şekiller YASAK):
   - TEMA HER YERDE HİSSEDİLECEK: Arka plan, düşmanlar, kuleler ve yol, fikirdeki temaya özgü öğelerle tasarlanacak. Örn. korsan teması: deniz dokusu, ahşap güverte yolu, yelkenli düşmanlar, palmiyeler; ortaçağ: taş surlar, bayraklar, meşaleler; uzay: yıldızlı boşluk, metalik panel zemin, neon ışıklar. Temadan bağımsız jenerik kare/daire kullanımı REDDEDİLİR.
   - Oyunun adı canvas üzerinde menüde ve oyun sırasında üst köşede görünecek.
   - Temaya özel 5-6 renklik hex paleti tanımla ve sadece onu kullan.
   - HER karakter (düşman, kule) en az 3-4 geometrik şeklin BİRLEŞİMİYLE çizilecek: örn. korsan gemisi düşmanı = gövde + yelken + direk + bayrak; kule = gövde + namlu + detay. Tek renkli tek kare/daire KESİNLİKLE YASAK.
   - Arka plan sahne gibi tasarlanacak: gradient gökyüzü + temaya uygun dekor öğeleri + yol/patika belirgin dokulu çizilecek.
   - Efektler: düşman ölümünde 8-12 parçacıklı patlama, mermilerde iz (trail), kule ateşlerken namlu parlaması, hasar alınca sayı uçuşması (floating damage text), BOSS'larda can barı.
   - Animasyon: düşmanlar yürüme/salınım animasyonlu, kuleler hedefe dönerek ateş eder, ctx.shadowBlur ile parlama/derinlik kullanılır.
9. DENGE: Dalga N'deki toplam düşman canı, mevcut kule gücüyle 20-30 saniyede eritilebilecek ve her dalgada %25-30 artacak şekilde formüle edilecek. Öldürülen düşman altın verir, altın ekonomisi yeni kule/yükseltme alımına yetecek şekilde dengelenir.
10. LİMİT: Kod 1200 satırı GEÇMEYECEK ama görsel detay ve oyun derinliği için bu alanı sonuna kadar KULLAN. ÇIKTI: Sadece saf kod; <!DOCTYPE html> ile başla, KESİNLİKLE </html> ile bitir. Markdown kullanma.
11. TEST ARAYÜZÜ: Global bir window.OYUN_DURUMU objesi tut ve her karede güncelle: {asama: "menu"|"oyunda"|"kazandi"|"kaybetti", dalga: sayı, can: sayı, skor: sayı}. Başlat butonuna id="baslaBtn" ver.
"""


def kod_uret_ve_test_et(fikir, client):
    """Oyunu üretir, truncation + LLM QA kontrolü yapar.
    Döner: (kod veya None, api_cagri_sayisi)"""
    hata_gecmisi = ""
    api_cagrisi = 0

    for deneme in range(1, MAX_DENEME + 1):
        print(f"🛠️ Üretim/Test döngüsü: {deneme}/{MAX_DENEME}")

        kod_prompt = f"""Sen uzman bir Oyun Geliştiricisisin. Şu konsepti tek bir index.html dosyasında eksiksiz, oynanabilir bir oyuna dönüştür: "{fikir}"
Önceki denemelerde alınan hatalar (varsa düzelt): {hata_gecmisi if hata_gecmisi else "Yok"}
{KOD_KURALLARI}"""

        cevap = gemini_cagir(client, MODEL, kod_prompt)
        api_cagrisi += 1

        kod = cevap.text.strip()
        kod = re.sub(r'^```html\s*|^```\s*|```$', '', kod, flags=re.MULTILINE).strip()

        # TEST A: Truncation
        if not kod.endswith("</html>"):
            print("❌ TEST A: Kod </html> ile bitmiyor.")
            hata_gecmisi += "\n- Kod yarıda kesildi; daha kısa ve öz yaz, </html> ile bitir."
            continue

        # TEST B: LLM QA
        print("🔍 Kalite Kontrol Ajanı inceliyor...")
        qa_prompt = f"""Aşağıdaki HTML/JS kodunda SyntaxError, ReferenceError veya oyun döngüsünü bozacak mantık hatası var mı?
Kusursuzsa Türkçe karakter KULLANMADAN SADECE "TEMIZ" yaz. Hata varsa hatayı ve çözümünü yaz.

Kod:
{kod}"""

        cevap_qa = gemini_cagir(client, MODEL, qa_prompt)
        api_cagrisi += 1
        qa = cevap_qa.text.strip()

        if "TEMIZ" in qa.upper():
            print("✅ TEST B: Kod onaylandı, robot oyuncu devreye giriyor...")

            # TEST C: Robot oyuncu gerçekten oynuyor
            os.makedirs("temp_test", exist_ok=True)
            test_yolu = os.path.join("temp_test", "index.html")
            with open(test_yolu, "w", encoding="utf-8") as f:
                f.write(kod)

            rapor = oyunu_test_et(test_yolu, client, MODEL, fikir)
            api_cagrisi += rapor["api_cagrisi"]

            if rapor["gecti"]:
                print(f"✅ TEST C: Robot oyuncu onayladı! Puan: {rapor['puan']}/10")
                return kod, api_cagrisi, rapor

            print(f"❌ TEST C: Robot oyuncu reddetti (Puan: {rapor['puan']}/10)")
            for s in rapor["sorunlar"][:5]:
                print(f"   - {s}")
            hata_gecmisi += "\n- Test oyuncusunun bulduğu sorunlar (düzelt): " \
                            + "; ".join(rapor["sorunlar"][:5])
            continue

        print(f"❌ QA hatası bulundu:\n{qa[:300]}")
        hata_gecmisi += f"\n- QA hatası: {qa}"

    print("🚨 Maksimum deneme aşıldı, geçerli kod üretilemedi.")
    return None, api_cagrisi, None


# ================== KAYIT + GALERİ ==================
def kaydet_ve_galeriyi_guncelle(oyun_adi, html_icerik):
    """Oyunu apps/slug/index.html'e kaydeder, manifest ve kök galeriyi günceller."""
    os.makedirs("apps", exist_ok=True)

    manifest_yolu = os.path.join("apps", "manifest.json")
    manifest = []
    if os.path.exists(manifest_yolu):
        with open(manifest_yolu, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    # Slug çakışması: varsa -2, -3 ekle
    slug = slugify(oyun_adi)
    mevcut_sluglar = {m["slug"] for m in manifest}
    temel, sayac = slug, 2
    while slug in mevcut_sluglar:
        slug = f"{temel}-{sayac}"
        sayac += 1

    klasor = os.path.join("apps", slug)
    os.makedirs(klasor, exist_ok=True)
    with open(os.path.join(klasor, "index.html"), "w", encoding="utf-8") as f:
        f.write(analytics_ekle(html_icerik))
    print(f"📁 Oyun kaydedildi: apps/{slug}/index.html")

    manifest.append({"isim": oyun_adi, "slug": slug,
                     "tarih": datetime.now().strftime("%Y-%m-%d")})
    with open(manifest_yolu, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Kök galeri
    kartlar = ""
    for m in reversed(manifest):  # en yeni üstte
        kartlar += f"""
            <a href="apps/{m['slug']}/index.html" class="block p-6 bg-white rounded-xl shadow-sm hover:shadow-md hover:-translate-y-1 transition-all border border-slate-200">
                <h2 class="text-xl font-semibold text-slate-800 mb-1">{m['isim']}</h2>
                <p class="text-xs text-slate-400 mb-2">{m['tarih']}</p>
                <span class="text-sm font-medium text-blue-600">Oyunu Başlat &rarr;</span>
            </a>"""

    galeri = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Savunma Oyunları Arşivi</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 font-sans text-slate-800">
<div class="max-w-5xl mx-auto px-4 py-16">
<h1 class="text-4xl font-bold text-center text-slate-900 mb-4">Savunma Oyunları Arşivi</h1>
<p class="text-center text-slate-600 mb-12">Yapay zeka tarafından her gün sıfırdan kodlanan, Canvas tabanlı tarayıcı savunma oyunları laboratuvarı.</p>
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">{kartlar}
</div>
</div>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(analytics_ekle(galeri))
    print("🌐 Galeri güncellendi.")
    return slug


# ================== GITHUB PUSH ==================
def github_repoya_gonder(slug):
    pat = os.environ.get("GITHUB_PAT")
    if not pat:
        raise ValueError("GITHUB_PAT ortam değişkeni bulunamadı.")

    g = Github(auth=Auth.Token(pat))
    repo = g.get_user().get_repo(REPO_ADI)
    mesaj = f"Yapay Zeka Yeni Oyun Uretti: {slug}"

    dosyalar = [
        f"apps/{slug}/index.html",
        "apps/manifest.json",
        "index.html",
    ]

    for yol in dosyalar:
        if not os.path.exists(yol):
            print(f"⚠️ {yol} lokalde yok, atlanıyor.")
            continue
        with open(yol, "r", encoding="utf-8") as f:
            icerik = f.read()
        try:
            mevcut = repo.get_contents(yol)
            repo.update_file(mevcut.path, mesaj, icerik, mevcut.sha)
            print(f"🔄 Güncellendi: {yol}")
        except GithubException as e:
            if e.status == 404:  # Dosya yok veya repo tamamen boş -> OLUŞTUR
                repo.create_file(yol, mesaj, icerik)
                print(f"✅ Eklendi: {yol}")
            else:
                raise

    print("🚀 Push tamamlandı.")


# ================== LOG ==================
def log_yaz(log_sekmesi, oyun_adi, api_sayisi, durum, not_=""):
    try:
        log_sekmesi.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            oyun_adi, str(api_sayisi), durum, not_ or "-",
        ])
        print(f"📊 Log: {durum} ({api_sayisi} API çağrısı)")
    except Exception as e:
        print(f"🚨 Log yazılamadı: {e}")


# ================== ANA AKIŞ ==================
def main():
    # FAILED logu NameError vermesin diye baştan tanımlı:
    oyun_adi = "BILINMIYOR"
    api_cagrisi = 0
    log_sekmesi = None

    try:
        # Gemini istemcisi (anahtar ortamdan)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY ortam değişkeni bulunamadı.")
        client = genai.Client(api_key=api_key)

        # Google Sheets bağlantısı
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        gc = gspread.authorize(creds)
        dosya = gc.open(SHEET_ADI)
        log_sekmesi = dosya.worksheet(LOG_SEKMESI)
        havuz = dosya.worksheet(HAVUZ_SEKMESI)

        # 1. Fikir al
        fikir = havuzdan_fikir_al(havuz)
        if not fikir:
            log_yaz(log_sekmesi, "HAVUZ BOS", 0, "FAILED", "Fikir havuzu tükendi!")
            return
        oyun_adi = fikirden_baslik(fikir)
        print(f"💡 Fikir: {fikir}")

        # 2. Üret + test et (QA + robot oyuncu)
        kod, api_cagrisi, rapor = kod_uret_ve_test_et(fikir, client)
        if kod is None:
            log_yaz(log_sekmesi, oyun_adi, api_cagrisi, "FAILED",
                    "3 denemede testleri geçen kod üretilemedi")
            return

        # 3. Kaydet + galeri + push
        slug = kaydet_ve_galeriyi_guncelle(oyun_adi, kod)
        github_repoya_gonder(slug)

        # 4. Başarı logu (robot oyuncunun puanı ve yorumuyla)
        log_yaz(log_sekmesi, oyun_adi, api_cagrisi, "BASARILI",
                f"Puan: {rapor['puan']}/10 - {rapor['yorum']}")

    except Exception as e:
        print(f"🚨 KRİTİK HATA: {e}")
        if log_sekmesi is not None:
            log_yaz(log_sekmesi, oyun_adi, api_cagrisi, "FAILED", str(e)[:200])
        raise  # Actions'ın da kırmızı görünmesi için


if __name__ == "__main__":
    main()
