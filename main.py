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
MAX_DENEME = 4
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
EKLENTI_KURALLARI = """
Sen uzman bir oyun sanatçısı ve JavaScript geliştiricisisin. Tam bir oyun YAZMAYACAKSIN.
Oyun motoru zaten hazır ve test edilmiş durumda (oyun döngüsü, dalgalar, kuleler, düşman
hareketi, çarpışma, HUD, menüler, mobil destek hepsi motorda). Senin tek görevin, motora
takılacak TEMA EKLENTİSİ yazmak: yani oyunun görünüşünü ve dengesini tanımlayan bir nesne.

ÇIKTI FORMATI: SADECE aşağıdaki yapıda tek bir JavaScript nesnesi yaz. Açıklama, markdown,
``` işareti KULLANMA. `const TEMA = {` ile başla ve `};` ile bitir. Sonuna `// SON` yaz.

const TEMA = {
  ad: "Oyunun Türkçe adı",
  aciklama: "Tek cümlelik Türkçe tanıtım",
  palet: { arka1:"#hex", arka2:"#hex", yol:"#hex", yolKenar:"#hex",
           dusman:"#hex", dusman2:"#hex", kule:"#hex", mermi:"#hex", vurgu:"#hex" },
  yol: [ {x:0,y:360}, {x:300,y:360}, ... , {x:1280,y:300} ],   // 1280x720 alanda 5-9 nokta,
        // ilk nokta soldan (x=0) veya üstten girmeli, son nokta ekrandan çıkmalı
  dusmanTipleri: [
    {ad:"Türkçe ad", can:60, hiz:62, altin:12, yaricap:14, renk:"#hex"},
    {ad:"Türkçe ad", can:42, hiz:96, altin:14, yaricap:12, renk:"#hex"},
    {ad:"Türkçe ad", can:155, hiz:44, altin:23, yaricap:18, renk:"#hex"}
  ],
  kuleTipleri: [
    {ad:"Türkçe ad", fiyat:50, menzil:150, hasar:18, atisHizi:1.2, mermiHizi:360, renk:"#hex"},
    {ad:"Türkçe ad", fiyat:90, menzil:125, hasar:44, atisHizi:0.55, mermiHizi:270, renk:"#hex", alan:48},
    {ad:"Türkçe ad", fiyat:70, menzil:135, hasar:8, atisHizi:0.9, mermiHizi:330, renk:"#hex", yavaslat:0.5}
  ],
  arkaplanCiz(c, W, H, t){ /* zorunlu */ },
  yolCiz(c, yol, t){ /* zorunlu */ },
  dusmanCiz(c, d, t){ /* zorunlu */ },
  kuleCiz(c, k, t){ /* zorunlu */ }
};
// SON

ÇİZİM KURALLARI (asıl işin bu, buraya yoğunlaş):
- c = canvas 2d context, W=1280, H=720, t = geçen saniye (animasyon için kullan).

* ÖLÇEK (kesin sınırlar, aşarsan oyun bozuk görünür):
  - kuleCiz: TÜM çizim (0,0) merkezli olacak ve -30..+30 piksel kutusunu AŞMAYACAK.
    Kule düşmandan en fazla 1.5 kat büyük görünmeli.
  - dusmanCiz: TÜM çizim (0,0) merkezli, yarıçapı d.yaricap*1.4'ü aşmayacak.
  - Bu sınırlar motorun tıklama alanıyla uyumludur; aşan çizim yanlış yerde görünür.

* NAMLU YÖNÜ (sık yapılan hata):
  - k.aci hedefin yönüdür ve 0 = SAĞ demektir. c.rotate(k.aci) çağırdıktan SONRA
    namluyu +X yönünde (sağa doğru, örn. c.fillRect(0,-4,26,8)) çiz. YUKARI (negatif y)
    çizersen kule yanlış yöne bakar. Taban ve gövdeyi rotate'ten ÖNCE çiz.

* KONTRAST (görünürlük kuralı, ihlal edilirse oyun oynanamaz):
  - Düşman renkleri arka plan renklerinden BELİRGİN ŞEKİLDE farklı olacak. Arka plan koyu
    ise düşmanlar açık/canlı, arka plan açık ise düşmanlar koyu olacak. Yeşil zeminde yeşil
    düşman, mavi gökte mavi düşman gibi eşleşmeler YASAK.
  - Her düşman ve kulenin etrafına ince koyu kontur (c.stroke) çiz ki zeminden ayrışsın.
  - palet.arka1 ve palet.arka2 birbirine yakın olabilir ama dusman/dusman2/kule renkleri
    onlardan uzak tonlarda olmalı.

* TEMA VARLIĞI:
  - Konseptteki ANA YAPI arkaplanCiz içinde görünür şekilde çizilecek: kale savunmasında
    surlar ve kapı, üs savunmasında üs binası, kovan savunmasında kovan gibi. Sadece
    genel manzara (dağ, bulut) yeterli DEĞİLDİR.
  - Yolun bittiği sağ/alt uçta savunulan yapı görünsün.

- arkaplanCiz: KATMANLI sahne çiz. Gradient gökyüzü/zemin + uzak silüetler + orta katman dekor
  + zemin dokusu + yukarıdaki ana yapı. t ile hafif animasyon ver (parlayan ışıklar, süzülen
  bulut, kıpırdayan su gibi). Sabit ve boş arka plan KABUL EDİLMEZ.
- yolCiz: yolu dokulu çiz (kenar + iç dolgu + üzerine tema deseni). Verilen `yol` dizisini kullan.
- dusmanCiz: d.x, d.y, d.yaricap, d.renk, d.bos (boss ise true), d.faz (animasyon fazı) verilir.
  Düşmanı EN AZ 4 parçadan oluştur (gövde + baş + detay + silah/kanat). Yürüme/salınım animasyonu
  için t ve d.faz kullan. Tek daire/kare KESİNLİKLE YASAK.
- kuleCiz: k.x, k.y, k.aci, k.tip.renk, k.seviye (1-3), k.flas (ateş anı) verilir.
  Kuleyi EN AZ 4 parçadan oluştur (taban + gövde + namlu + detay). k.flas>0 iken namlu ucunda
  parlama çiz. k.seviye arttıkça görsel detay ekle.
- Gölge, kontur ve c.shadowBlur ile derinlik ver. Renkler paletle uyumlu olsun.
- Her çizim fonksiyonu c.save() ile başlayıp c.restore() ile bitmeli (dönüşüm sızmasın).
- Not: motor çizimden önce c.translate(x,y) YAPMAZ; sen kendi save/translate'ini yaparsın.

DENGE KURALLARI: Yukarıdaki sayısal aralıkları koru (düşman hızı 40-100, kule menzili 110-160,
mermi hızı 250-400). Sadece temaya uygun isim ve renk değiştir, aşırı değer verme.

YASAKLAR: Dış dosya/kütüphane, emoji, resim, ses YOK. window/document'e dokunma, oyun döngüsü
yazma, setInterval kullanma. Sadece yukarıdaki TEMA nesnesini üret.
"""


def motor_sablonu_oku():
    with open("motor_sablon.html", "r", encoding="utf-8") as f:
        sablon = f.read()
    # Şablon bütünlük kontrolü: eksik/bozuk yapıştırmayı erken yakala
    for zorunlu in ("<canvas", "__TEMA_EKLENTISI__", "__OYUN_ADI__",
                    "baslaBtn", "</html>"):
        if zorunlu not in sablon:
            raise ValueError(
                f"motor_sablon.html bozuk veya eksik: '{zorunlu}' bulunamadı. "
                "Dosyayı yeniden yükleyin.")
    return sablon


def oyun_olustur(eklenti_kodu, oyun_adi):
    """Tema eklentisini test edilmiş motora enjekte edip tam oyun HTML'i üretir."""
    sablon = motor_sablonu_oku()
    return (sablon.replace("__TEMA_EKLENTISI__", eklenti_kodu)
                  .replace("__OYUN_ADI__", oyun_adi))


def eklenti_temizle(ham):
    """Gemini çıktısındaki markdown ve fazlalıkları temizler."""
    kod = re.sub(r'^```(?:javascript|js)?\s*|```$', '', ham.strip(), flags=re.MULTILINE).strip()
    kod = kod.replace("// SON", "").strip()
    bas = kod.find("const TEMA")
    if bas > 0:
        kod = kod[bas:]
    return kod


def eklenti_gecerli_mi(kod):
    """Eklentinin yapısal olarak sağlam olup olmadığını kontrol eder."""
    if not kod.startswith("const TEMA"):
        return "Eklenti 'const TEMA' ile başlamıyor"
    if kod.count("{") != kod.count("}"):
        return "Süslü parantezler eşleşmiyor (kod yarıda kesilmiş olabilir)"
    for zorunlu in ("arkaplanCiz", "yolCiz", "dusmanCiz", "kuleCiz",
                    "dusmanTipleri", "kuleTipleri", "palet"):
        if zorunlu not in kod:
            return f"Zorunlu alan eksik: {zorunlu}"
    for yasak in ("requestAnimationFrame", "setInterval", "document.", "window."):
        if yasak in kod:
            return f"Yasak ifade kullanılmış: {yasak}"
    return None


def eklenti_uret_ve_test_et(fikir, client):
    """Tema eklentisi üretir, motora takar, robot oyuncuyla test eder.
    Döner: (tam oyun kodu veya None, api_cagri_sayisi, rapor veya hata özeti)"""
    hata_gecmisi = ""
    api_cagrisi = 0
    deneme_ozetleri = []

    for deneme in range(1, MAX_DENEME + 1):
        print(f"🛠️ Eklenti üretimi: {deneme}/{MAX_DENEME}")

        prompt = f"""Oyun konsepti: "{fikir}"
Önceki denemelerde alınan hatalar (varsa düzelt): {hata_gecmisi if hata_gecmisi else "Yok"}
{EKLENTI_KURALLARI}"""

        cevap = gemini_cagir(client, MODEL, prompt)
        api_cagrisi += 1
        eklenti = eklenti_temizle(cevap.text)

        # TEST A: Yapısal geçerlilik (API çağrısı harcamaz)
        sorun = eklenti_gecerli_mi(eklenti)
        if sorun:
            print(f"❌ TEST A: {sorun}")
            deneme_ozetleri.append(f"D{deneme}:YAPI {sorun[:40]}")
            hata_gecmisi += f"\n- {sorun}. Formatı tam olarak istenen şekilde üret."
            continue

        # TEST B: Motora tak ve robot oyuncuyla gerçek testten geçir
        oyun_adi = fikirden_baslik(fikir)
        tam_oyun = oyun_olustur(eklenti, oyun_adi)
        os.makedirs("temp_test", exist_ok=True)
        test_yolu = os.path.join("temp_test", "index.html")
        with open(test_yolu, "w", encoding="utf-8") as f:
            f.write(tam_oyun)

        print("🤖 Robot oyuncu test ediyor...")
        rapor = oyunu_test_et(test_yolu, client, MODEL, fikir)
        api_cagrisi += rapor["api_cagrisi"]

        if rapor["gecti"]:
            print(f"✅ Test geçildi! Puan: {rapor['puan']}/10")
            rapor["eklenti"] = eklenti
            return tam_oyun, api_cagrisi, rapor

        print(f"❌ Robot reddetti (Puan: {rapor['puan']}/10)")
        for s in rapor["sorunlar"][:4]:
            print(f"   - {s}")
        ilk = rapor["sorunlar"][0][:60] if rapor["sorunlar"] else "?"
        deneme_ozetleri.append(f"D{deneme}:ROBOT(p{rapor['puan']}) {ilk}")
        hata_gecmisi += "\n- Test sonucu sorunlar (çizimleri düzelt): " \
                        + "; ".join(rapor["sorunlar"][:4])

    print("🚨 Maksimum deneme aşıldı.")
    return None, api_cagrisi, " | ".join(deneme_ozetleri)


def eklenti_cilala(fikir, eklenti_kodu, client):
    """Testi geçen eklentinin SADECE çizim fonksiyonlarını zenginleştirir."""
    prompt = f"""Aşağıda testleri geçmiş, çalışan bir oyun tema eklentisi var.
Konsept: "{fikir}"

Görevin: YAPIYA VE SAYISAL DEĞERLERE HİÇ DOKUNMADAN, sadece çizim fonksiyonlarını
(arkaplanCiz, yolCiz, dusmanCiz, kuleCiz) görsel olarak zenginleştirmek:
- Arka plana bir katman daha ekle (uzak siluet, gökyüzü detayı, zemin dokusu) ve t ile
  yumuşak animasyon ver.
- Düşman ve kulelere ek detay katmanları koy (kontur, iç desen, ışık vurgusu, gölge).
- Renk geçişleri (createLinearGradient / createRadialGradient) ve c.shadowBlur kullanarak
  derinlik kat.
- Kule seviyesine (k.seviye) göre görsel farklılık ekle.

DEĞİŞMEZ: Nesne yapısı, alan isimleri, palet dışındaki sayısal değerler, yol dizisi,
düşman/kule istatistikleri AYNI kalacak. Fonksiyonlar c.save()/c.restore() dengesini koruyacak.
Dış kaynak, emoji, document/window kullanımı YOK.

ÇIKTI: SADECE güncellenmiş eklenti kodu. `const TEMA = {{` ile başla, `}};` ile bitir,
sonuna `// SON` yaz. Markdown kullanma.

MEVCUT EKLENTİ:
{eklenti_kodu}"""
    cevap = gemini_cagir(client, MODEL, prompt)
    yeni = eklenti_temizle(cevap.text)
    return None if eklenti_gecerli_mi(yeni) else yeni

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

        # 2. Tema eklentisi üret + motora tak + robot oyuncuyla test et
        kod, api_cagrisi, rapor = eklenti_uret_ve_test_et(fikir, client)
        if kod is None:
            sebep = rapor if isinstance(rapor, str) else "Sebep kaydedilemedi"
            log_yaz(log_sekmesi, oyun_adi, api_cagrisi, "FAILED", sebep[:250])
            return

        # 2.5 CİLA: Çalışan eklentinin çizimlerini zenginleştir.
        # Cilalı sürüm testi geçer ve puanı düşmezse o yayınlanır, yoksa orijinal kalır.
        try:
            print("✨ Cila aşaması: grafikler zenginleştiriliyor...")
            mevcut_eklenti = rapor.get("eklenti") or ""
            cilali_eklenti = eklenti_cilala(fikir, mevcut_eklenti, client) \
                if mevcut_eklenti else None
            api_cagrisi += 1
            if cilali_eklenti:
                cilali_oyun = oyun_olustur(cilali_eklenti, oyun_adi)
                os.makedirs("temp_test", exist_ok=True)
                cila_yolu = os.path.join("temp_test", "cila.html")
                with open(cila_yolu, "w", encoding="utf-8") as f:
                    f.write(cilali_oyun)
                cila_rapor = oyunu_test_et(cila_yolu, client, MODEL, fikir)
                api_cagrisi += cila_rapor["api_cagrisi"]
                if cila_rapor["gecti"] and cila_rapor["puan"] >= rapor["puan"]:
                    kod, rapor = cilali_oyun, cila_rapor
                    print(f"✨ Cilalı sürüm kabul edildi! Puan: {rapor['puan']}/10")
                else:
                    print("✨ Cilalı sürüm barajı geçemedi, orijinal yayınlanacak.")
            else:
                print("✨ Cila çıktısı geçersiz, orijinal yayınlanacak.")
        except Exception as cila_hata:
            print(f"✨ Cila aşaması atlandı ({cila_hata}), orijinal yayınlanacak.")

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
