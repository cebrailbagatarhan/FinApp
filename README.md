# FinApp

Türkiye ve ABD piyasaları için veri toplama, enflasyon karşılaştırması, teknik gösterge incelemesi ve Streamlit görselleştirmesi sunan eğitim/araştırma projesi.

> [!WARNING]
> Uygulamadaki **Buy/Sell** etiketleri doğrulanmış yatırım tavsiyesi değildir. RSI/MACD ve enflasyon kurallarından üretilen araştırma hipotezleridir. Bir sinyal, zaman sıralı ve maliyetli backtest sonucu olmadan “başarılı” kabul edilmez.

## Kapsam

- Market fiyatlarını scrape ederek deneysel market enflasyonu serisi oluşturma
- Resmî makro verilerle karşılaştırma
- BIST ve ABD hisseleri için RSI/MACD gösterimi
- Kural tabanlı sinyal üretimi
- Streamlit dashboard
- Next-bar, transaction cost ve slippage içeren tek-hisse backtest'i

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python database.py
streamlit run app.py
```

Canlı TCMB/EVDS verisi opsiyoneldir. Anahtarı repoya yazmayın:

```bash
cp .env.example .env
# .env içinde EVDS_API_KEY değerini tanımlayın
```

## Dashboard

| Sayfa | Amaç |
| --- | --- |
| Ana sayfa | Veri kapsamı ve son göstergeler |
| Market enflasyonu | Scrape edilen fiyat değişimleri ile resmî seriyi karşılaştırma |
| Hisseler | Fiyat, RSI ve MACD görselleştirmeleri |
| Sinyaller | Kural tabanlı araştırma sinyallerini filtreleme |
| Veri güncelleme | Scraper ve piyasa veri akışlarını çalıştırma |

## Backtest

`analysis/backtest.py`, sinyali **t gününün kapanışında** gözlenmiş kabul eder ve pozisyonu ancak **t+1 getirisinde** uygular. Böylece aynı barın kapanış fiyatını hem sinyal üretip hem de daha önce işlem yapılmış gibi kullanmaz.

SQLite'taki bir ticker için:

```bash
python -m analysis.backtest \
  --ticker THYAO.IS \
  --start 2022-01-01 \
  --end 2025-12-31 \
  --evaluation-start 2024-01-01 \
  --commission-bps 10 \
  --slippage-bps 5
```

CSV ile:

```bash
python -m analysis.backtest \
  --csv prices-and-signals.csv \
  --evaluation-start 2024-01-01
```

Gerekli CSV alanları `date` ve `close_price`dır. `signal` yoksa aynı satırdaki `rsi_value`, `macd_value` ve `macd_signal` değerlerinden mevcut kurala denk bir sinyal oluşturulur.

Çıktılar:

- günlük pozisyon, turnover, maliyet, strateji getirisi, equity ve drawdown CSV'si
- total/annualized return, volatility, Sharpe, max drawdown, buy-and-hold farkı ve trade istatistikleri JSON'u
- `--evaluation-start` verilirse development ve out-of-sample evaluation pencereleri ayrı raporlanır

Testler:

```bash
python -m unittest discover -s tests -v
```

## Backtest varsayımları

- Long veya nakit; short ve kaldıraç yoktur.
- Commission ve slippage tek yönlü basis point olarak her pozisyon değişiminde düşülür.
- Varsayılan getiri close-to-close'dur; kaynak fiyat serisi düzeltilmemişse temettü/split etkileri ayrıca ele alınmalıdır.
- Açık pozisyon varsayılan olarak son gözlemde tasfiye maliyetiyle kapatılır.
- Risk-free oran varsayılan sıfırdır ve CLI ile değiştirilebilir.
- Parametreler bu scriptte optimize edilmez; eşik seçimi yapılacaksa development penceresinde yapılmalı ve evaluation penceresine dokunulmamalıdır.

## Sonuç durumu

Repoya henüz sabit veri snapshot'ı ve ham equity çıktısıyla doğrulanmış backtest sonucu commit edilmemiştir. Bu nedenle README herhangi bir Sharpe, getiri veya “sinyal doğruluğu” iddiası yayımlamaz.

## Bilinen yanlılıklar

- Varsayılan takip listesi bugünkü ticker'lardan oluşur; bu, portföy karşılaştırmasında survivorship bias yaratabilir.
- Ücretsiz veri kaynaklarında delist edilmiş hisseler, temettü ve split düzeltmeleri eksik olabilir.
- Scrape edilen market sepeti resmî TÜFE metodolojisinin yerine geçmez.
- Tek ticker backtest'i portföy performansı, likidite veya piyasa etkisini kanıtlamaz.
- Sinyal kuralları öğrenilmiş model değildir; geçmişe göre eşik ayarı overfitting yaratabilir.

## Proje yapısı

```text
analysis/
  backtest.py          # maliyetli, next-bar backtest
  signals.py           # kural tabanlı canlı sinyaller
  inflation_calc.py    # enflasyon karşılaştırması
scrapers/              # market ve makro veri kaynakları
app.py                 # Streamlit dashboard
database.py            # SQLite şeması ve veri erişimi
tests/                 # backtest regresyon testleri
```

## Sorumluluk reddi

Bu proje eğitim amaçlıdır; yatırım tavsiyesi değildir. Gerçek işlem kararı için kullanılmamalıdır.

