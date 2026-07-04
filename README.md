# FinApp - Finansal Analiz Uygulaması 📈

Türkiye ve ABD piyasalarını analiz eden, market enflasyonu ile resmi enflasyonu karşılaştıran ve al/sat sinyalleri üreten kapsamlı bir finansal analiz aracı.

## 🚀 Özellikler

- **Market Enflasyonu Takibi**: Süpermarket fiyatlarını scrape ederek gerçek enflasyonu hesaplar
- **Borsa Analizi**: BIST ve ABD hisselerini RSI, MACD gibi indikatörlerle analiz eder
- **Akıllı Sinyaller**: Enflasyon + teknik analiz kombinasyonuyla al/sat sinyalleri üretir
- **Interaktif Dashboard**: Streamlit ile görsel ve kullanıcı dostu arayüz

## 📁 Proje Yapısı

```
FinApp/
├── data/                   # SQLite veritabanı
├── scrapers/
│   ├── market_scraper.py   # Migros/market fiyat botu
│   └── macro_data.py       # Borsa ve makro veri API'leri
├── analysis/
│   ├── inflation_calc.py   # Enflasyon hesaplama motoru
│   └── signals.py          # Al/Sat sinyal mekanizması
├── database.py             # Veritabanı işlemleri
├── app.py                  # Streamlit dashboard
├── run.py                  # Kolay başlatma scripti
└── requirements.txt        # Gerekli kütüphaneler
```

## 🛠️ Kurulum

### 1. Gerekli kütüphaneleri yükle

```bash
cd FinApp
pip install -r requirements.txt
```

### 2. Veritabanını başlat

```bash
python database.py
```

### 2b. EVDS API anahtarı (opsiyonel, canlı TCMB verisi için)

```bash
# .env.example dosyasını .env olarak kopyalayın ve anahtarınızı girin
copy .env.example .env
# Windows PowerShell:
$env:EVDS_API_KEY="your_key_here"
```

Anahtar: https://evds.tcmb.gov.tr

### 3. Örnek veri yükle (opsiyonel)

```bash
python scrapers/market_scraper.py
python scrapers/macro_data.py
```

### 4. Dashboard'u başlat

```bash
streamlit run app.py
```

veya

```bash
python run.py
```

## 📊 Kullanım

### Dashboard Sayfaları

1. **Ana Sayfa**: Genel özet, enflasyon karşılaştırması, al önerileri
2. **Market Enflasyonu**: Ürün fiyat değişimleri, resmi enflasyonla karşılaştırma
3. **Hisse Senetleri**: Candlestick grafikleri, RSI, MACD analizi
4. **Sinyaller**: Filtrelenebilir al/sat sinyalleri
5. **Veri Güncelle**: Verileri güncel tutma araçları

### Takip Edilen Hisseler

**Türkiye (BIST)**:
- THYAO (Türk Hava Yolları)
- GARAN (Garanti Bankası)
- AKBNK (Akbank)
- TUPRS (Tüpraş)
- EREGL (Ereğli Demir Çelik)

**ABD**:
- AAPL (Apple)
- MSFT (Microsoft)
- GOOGL (Google)
- AMZN (Amazon)
- TSLA (Tesla)

## 🔧 Özelleştirme

### Yeni hisse eklemek

[scrapers/macro_data.py](scrapers/macro_data.py) dosyasında `TICKERS` sözlüğüne ekleyin:

```python
TICKERS = {
    "TR": ["THYAO.IS", "GARAN.IS", ...],  # .IS uzantısı BIST için
    "US": ["AAPL", "MSFT", ...]
}
```

### Sinyal stratejisini değiştirmek

[analysis/signals.py](analysis/signals.py) dosyasında `generate_combined_signals()` fonksiyonunu düzenleyin.

## ⚠️ Önemli Notlar

1. **Yatırım Tavsiyesi Değildir**: Bu uygulama eğitim amaçlıdır.
2. **Web Scraping**: Market scraping sitelerin şartlarına uygun kullanılmalıdır.
3. **API Limitleri**: yfinance ücretsiz API limitine tabidir.

## 🛡️ Lisans

MIT License

## 📧 İletişim

Sorularınız için issue açabilirsiniz.
