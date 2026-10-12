# -*- coding: utf-8 -*-
"""
AI OYUN FABRİKASI - main.py (v3)
Günde 1 kez çalışır: Sheets'teki fikir havuzundan fikir alır,
Gemini ile oyun üretir, test eder, GitHub'a push eder, loglar.

v3: motor_sablon.html v3 (3 harita × 3 bölüm × 4 dalga, MEKANİK KANCALARI, kalibre denge).
    Eklenti artık fikrin mekaniğini de yazar; kalite testi mekaniğin gerçekten çalıştığını ölçer.
    Model: Gemini 3.8 Flash (ücretsiz katman) + otomatik yedek modeller.
    Başarısız fikir yanmaz: bir kez daha denenir (TEKRAR), sonra BASARISIZ işaretlenir.

Gerekli ortam değişkenleri:
  GEMINI_API_KEY : Google AI Studio API anahtarı
  GITHUB_PAT     : GitHub Personal Access Token
Gerekli dosya:
  credentials.json : Google Hizmet Hesabı anahtarı (Actions'ta base64'ten üretilir)
"""

import os
import re
import json
import glob
import shutil
import hashlib
import subprocess
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from github import Github, Auth
from github.GithubException import GithubException
from google import genai

from test_bot import oyunu_test_et, gemini_cagir


class _Yanit:
    def __init__(self, text):
        self.text = text


def yazar_cagir(client, prompt):
    """Eklentiyi yazdırır. ANTHROPIC_API_KEY varsa Claude, yoksa (ya da Claude hata verirse) Gemini."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            ac = anthropic.Anthropic()          # anahtarı ortamdan okur
            parcalar = []
            # Uzun çıktıda zaman aşımı olmasın diye akış (stream) kullanılır
            with ac.messages.stream(model=CLAUDE_MODEL, max_tokens=CLAUDE_MAX_TOKEN,
                                    messages=[{"role": "user", "content": prompt}]) as akis:
                for parca in akis.text_stream:
                    parcalar.append(parca)
                son = akis.get_final_message()
            metin = "".join(parcalar)
            k = son.usage
            maliyet_usd = (k.input_tokens * (4 if "opus" in CLAUDE_MODEL else 2)
                           + k.output_tokens * (20 if "opus" in CLAUDE_MODEL else 10)) / 1e6
            print(f"🟣 Claude ({CLAUDE_MODEL}): {k.input_tokens} girdi + {k.output_tokens} çıktı token "
                  f"≈ ${maliyet_usd:.3f}")
            if metin.strip():
                gemini_cagir.son_model = CLAUDE_MODEL
                return _Yanit(metin)
            print("⚠️ Claude boş yanıt döndürdü, Gemini'ye geçiliyor.")
        except Exception as e:
            print(f"⚠️ Claude çağrısı başarısız ({str(e)[:150]}), Gemini'ye geçiliyor.")
    return gemini_cagir(client, MODEL, prompt)

# ================== AYARLAR ==================
SHEET_ADI = "AI Uygulama Fabrikası"   # Google Sheets dosya adı
LOG_SEKMESI = "Loglar"                # Log sekmesi (A:Tarih B:Oyun C:API D:Durum E:Not)
HAVUZ_SEKMESI = "FikirHavuzu"         # Fikir havuzu (A:Fikir B:Durum)
REPO_ADI = "ai-oyun-fabrikasi"        # GitHub repo adı
# v3: modeller sıralı listedir; ilki kota/erişim sorunu verirse sonrakine geçilir.
# Eklentiyi yazan model (günde en çok ~6 çağrı) ve ekran görüntüsünü puanlayan model ayrı
# tutulur: ücretsiz katmanda kotalar model başınadır, böylece birbirinin hakkını yemezler.
# GitHub > Settings > Secrets and variables > Actions > Variables bölümüne GEMINI_MODEL
# eklenirse listenin başına o model geçer (kod değiştirmeden model denemek için).
YAZAR_MODELLER = [m for m in (os.environ.get("GEMINI_MODEL"), "gemini-3.8-flash",
                              "gemini-3.6-flash", "gemini-2.5-flash") if m]
GOZ_MODELLER = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-2.5-flash"]
MODEL = YAZAR_MODELLER                # geriye uyum: eski çağrılar listeyi alır

# İSTEĞE BAĞLI CLAUDE (ücretli): GitHub Secrets'a ANTHROPIC_API_KEY eklenirse eklentiyi
# Claude yazar; Gemini yalnız ekran görüntüsü puanlamada (ücretsiz) kalır. Anahtar yoksa
# fabrika eskisi gibi tamamen Gemini ile çalışır. Claude hata verirse o çağrı Gemini'ye düşer.
# Variables bölümüne CLAUDE_MODEL eklenerek model değiştirilebilir (ör. claude-opus-5-5).
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
CLAUDE_MAX_TOKEN = 32000              # bir eklenti ~10-20 bin token; üst sınır maliyeti de sınırlar
MAX_DENEME = 4
ORNEK_KLASORU = "ornekler"            # Prompt'a örnek olarak giren referans eklentiler
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
    """v3: B sütunu boş olan ilk fikri alır; yoksa bir kez başarısız olmuş (TEKRAR) fikri alır.
    Döner: (satır_no, fikir, önceki_durum) ya da None. Durum sonuçta durum_yaz() ile işaretlenir:
    başarı → KULLANILDI, ilk başarısızlık → TEKRAR, ikinci başarısızlık → BASARISIZ.
    (v1/v2'de fikir üretimden ÖNCE KULLANILDI yapılıyordu; başarısız günler fikir yakıyordu.)"""
    satirlar = havuz.get_all_values()
    adaylar = []
    for i, satir in enumerate(satirlar, start=1):
        fikir = satir[0].strip() if len(satir) > 0 else ""
        durum = satir[1].strip().upper() if len(satir) > 1 else ""
        if not fikir or fikir.lower().startswith("fikir"):     # başlık satırı
            continue
        if durum == "":
            return (i, fikir, "")
        if durum == "TEKRAR":
            adaylar.append((i, fikir, "TEKRAR"))
    return adaylar[0] if adaylar else None


def durum_yaz(havuz, satir_no, durum):
    try:
        havuz.update_cell(satir_no, 2, durum)
    except Exception as e:
        print(f"⚠️ Fikir durumu yazılamadı: {e}")


# ================== ÜRETİM + KALİTE KONTROL ==================
# v3: Gemini'ye giden kurallar ayrı dosyada (Python'a dokunmadan düzenlenebilsin diye).
KURAL_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eklenti_kurallari.txt")
if not os.path.exists(KURAL_DOSYASI):
    raise FileNotFoundError("eklenti_kurallari.txt bulunamadı: main.py ile aynı klasöre yükleyin.")
with open(KURAL_DOSYASI, encoding="utf-8") as _f:
    EKLENTI_KURALLARI = _f.read()



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


def js_sozdizimi_hatasi(kod):
    """v3: Node varsa eklentiyi tarayıcıya vermeden önce sözdizimi denetimi (kesilmiş çıktıyı
    ve eksik parantezi Playwright'a hiç sokmadan yakalar). Node yoksa sessizce geçer."""
    node = shutil.which("node")
    if not node:
        return None
    os.makedirs("temp_test", exist_ok=True)
    yol = os.path.join("temp_test", "eklenti_kontrol.js")
    with open(yol, "w", encoding="utf-8") as f:
        f.write(kod + "\n;module.exports = TEMA;\n")
    try:
        r = subprocess.run([node, "--check", yol], capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode == 0:
        return None
    satirlar = [x for x in (r.stderr or "").splitlines() if x.strip()]
    return "JavaScript sözdizimi hatası: " + " | ".join(satirlar[-3:])[:220]


def eklenti_gecerli_mi(kod):
    """Eklentinin yapısal olarak sağlam olup olmadığını kontrol eder."""
    if not kod.startswith("const TEMA"):
        return "Eklenti 'const TEMA' ile başlamıyor"
    if kod.count("{") != kod.count("}"):
        return "Süslü parantezler eşleşmiyor (kod yarıda kesilmiş olabilir)"
    for zorunlu in ("arkaplanCiz", "yolCiz", "dusmanCiz", "kuleCiz",
                    "dusmanTipleri", "kuleTipleri", "palet", "haritalar", "mekanik"):
        if zorunlu not in kod:
            return f"Zorunlu alan eksik: {zorunlu}"
    for yasak in ("requestAnimationFrame", "setInterval", "setTimeout", "document.", "window.",
                  "fetch(", "XMLHttpRequest", "localStorage"):
        if yasak in kod:
            return f"Yasak ifade kullanılmış: {yasak}"
    return js_sozdizimi_hatasi(kod)


def ornek_eklenti_sec(fikir):
    """v3: ornekler/ klasöründen bir referans eklenti seçer (fikre göre sabit, örnekler dönüşümlü).
    Bu klasör fabrikanın 'örnek kütüphanesi'dir: en iyi oyunların eklentileri buraya eklendikçe
    sonraki üretimler o çıtadan başlar."""
    dosyalar = sorted(glob.glob(os.path.join(ORNEK_KLASORU, "*.js")))
    if not dosyalar:
        return ""
    i = int(hashlib.md5(fikir.encode("utf-8")).hexdigest(), 16) % len(dosyalar)
    with open(dosyalar[i], encoding="utf-8") as f:
        return f.read()


def eklenti_uret_ve_test_et(fikir, client):
    """Tema eklentisi üretir, motora takar, robot oyuncuyla test eder.
    Döner: (tam oyun kodu veya None, api_cagri_sayisi, rapor veya hata özeti)"""
    hata_gecmisi = ""
    api_cagrisi = 0
    deneme_ozetleri = []

    for deneme in range(1, MAX_DENEME + 1):
        print(f"🛠️ Eklenti üretimi: {deneme}/{MAX_DENEME}")

        ornek = ornek_eklenti_sec(fikir)
        prompt = f"""Oyun konsepti (BAŞLIK; KANCA; MEKANİK; HARİTALAR; İMZA KULE; İMZA DÜŞMAN):
"{fikir}"

Önceki denemelerde alınan hatalar (varsa MUTLAKA düzelt): {hata_gecmisi if hata_gecmisi else "Yok"}

{EKLENTI_KURALLARI}

ÖRNEK EKLENTİ — yalnız YAPIYI, mekanik kancalarının kullanımını ve çizim kalitesi çıtasını göster.
Tema, çizimler, renkler, yollar ve isimler KOPYALANMAYACAK; senin oyunun tamamen farklı görünmeli:
{ornek}"""

        cevap = yazar_cagir(client, prompt)
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
        rapor = oyunu_test_et(test_yolu, client, GOZ_MODELLER, fikir)
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

DEĞİŞMEZ: Nesne yapısı, alan isimleri, palet dışındaki sayısal değerler, haritalar ve yol
dizileri, düşman/kule istatistikleri ve `mekanik` nesnesinin TAMAMI AYNI kalacak (mekanik
koduna dokunma). Fonksiyonlar c.save()/c.restore() dengesini koruyacak. Düşman ve kule
gövdeleri opak kalacak; tipe göre dallanmada son dal koşulsuz `else` kalacak.
Dış kaynak, emoji, document/window kullanımı YOK.

ÇIKTI: SADECE güncellenmiş eklenti kodu. `const TEMA = {{` ile başla, `}};` ile bitir,
sonuna `// SON` yaz. Markdown kullanma.

MEVCUT EKLENTİ:
{eklenti_kodu}"""
    cevap = yazar_cagir(client, prompt)
    yeni = eklenti_temizle(cevap.text)
    return None if eklenti_gecerli_mi(yeni) else yeni

# ================== KAYIT + GALERİ ==================
def kaydet_ve_galeriyi_guncelle(oyun_adi, html_icerik, kapak_png=None):
    """Oyunu apps/slug/index.html'e kaydeder, manifest ve kök galeriyi günceller.
    kapak_png verilirse (robot oyuncunun zaten çektiği ekran görüntüsü — ek maliyet
    yok) apps/slug/kapak.png olarak da kaydedilir ve galeri kartında gösterilir."""
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

    kapak_var = False
    if kapak_png:
        with open(os.path.join(klasor, "kapak.png"), "wb") as f:
            f.write(kapak_png)
        kapak_var = True
        print(f"🖼️ Kapak resmi kaydedildi: apps/{slug}/kapak.png")

    manifest.append({"isim": oyun_adi, "slug": slug, "kapak": kapak_var,
                     "tarih": datetime.now().strftime("%Y-%m-%d")})
    with open(manifest_yolu, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Kök galeri
    kartlar = ""
    for m in reversed(manifest):  # en yeni üstte
        gorsel = (f'<img src="apps/{m["slug"]}/kapak.png" loading="lazy" '
                  f'class="w-full h-36 object-cover rounded-lg mb-3" alt="{m["isim"]}">'
                  if m.get("kapak") else
                  '<div class="w-full h-36 rounded-lg mb-3 bg-gradient-to-br '
                  'from-slate-200 to-slate-300"></div>')
        kartlar += f"""
            <a href="apps/{m['slug']}/index.html" class="block p-4 bg-white rounded-xl shadow-sm hover:shadow-md hover:-translate-y-1 transition-all border border-slate-200">
                {gorsel}
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
        f"apps/{slug}/kapak.png",   # Varsa robot oyuncunun ekran görüntüsü; yoksa atlanır
        "apps/manifest.json",
        "index.html",
    ]

    for yol in dosyalar:
        if not os.path.exists(yol):
            if not yol.endswith("kapak.png"):  # kapak.png'nin olmaması normal, uyarı vermeye gerek yok
                print(f"⚠️ {yol} lokalde yok, atlanıyor.")
            continue
        ikili = yol.endswith(".png")
        with open(yol, "rb" if ikili else "r", **({} if ikili else {"encoding": "utf-8"})) as f:
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
        # 7 dk zaman sınırı: yanıt hiç gelmezse fabrika saatlerce asılı kalmasın
        client = genai.Client(api_key=api_key, http_options={"timeout": 420_000})

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
        satir_no, fikir, onceki_durum = fikir
        oyun_adi = fikirden_baslik(fikir)
        print(f"💡 Fikir (satır {satir_no}{', ikinci deneme' if onceki_durum else ''}): {fikir}")

        # 2. Tema eklentisi üret + motora tak + robot oyuncuyla test et
        kod, api_cagrisi, rapor = eklenti_uret_ve_test_et(fikir, client)
        if kod is None:
            sebep = rapor if isinstance(rapor, str) else "Sebep kaydedilemedi"
            durum_yaz(havuz, satir_no, "BASARISIZ" if onceki_durum == "TEKRAR" else "TEKRAR")
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
                cila_rapor = oyunu_test_et(cila_yolu, client, GOZ_MODELLER, fikir)
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

        # 3. Kaydet + galeri + push (kapak: robot oyuncunun zaten çektiği ekran görüntüsü)
        slug = kaydet_ve_galeriyi_guncelle(oyun_adi, kod, rapor.get("kapak_png"))
        github_repoya_gonder(slug)
        durum_yaz(havuz, satir_no, "KULLANILDI")

        # 4. Başarı logu (robot oyuncunun puanı ve yorumuyla)
        mk = rapor.get("mekanik_ozet") or {}
        log_yaz(log_sekmesi, oyun_adi, api_cagrisi, "BASARILI",
                f"Puan: {rapor['puan']}/10 - {rapor['yorum']} | Model: {gemini_cagir.son_model}"
                f" | Mekanik: {mk.get('mekanik')} | Bot: {mk.get('bot')}")

    except Exception as e:
        print(f"🚨 KRİTİK HATA: {e}")
        if log_sekmesi is not None:
            log_yaz(log_sekmesi, oyun_adi, api_cagrisi, "FAILED", str(e)[:200])
        raise  # Actions'ın da kırmızı görünmesi için


if __name__ == "__main__":
    main()
