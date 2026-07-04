"""
Dinamik Borsa Analizi - Arama Motoru Modu
Kullanıcının yazdığı herhangi bir hisse kodunu analiz eder.
"""

import sys
import os
import pandas as pd
import yfinance as yf
import ta
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, insert_stock_data


def normalize_ticker(ticker: str, market: str = "auto") -> str:
    """
    Hisse kodunu normalize eder.
    BIST hisseleri için .IS ekler, ABD hisseleri için dokunmaz.
    
    Args:
        ticker: Kullanıcının girdiği hisse kodu (THYAO, AAPL vs.)
        market: 'bist', 'us' veya 'auto' (otomatik algıla)
    
    Returns:
        Yahoo Finance formatında ticker
    """
    ticker = ticker.upper().strip()
    
    # Zaten .IS veya . içeriyorsa dokunma
    if '.' in ticker:
        return ticker
    
    if market == "bist":
        return f"{ticker}.IS"
    elif market == "us":
        return ticker
    else:
        # Otomatik algılama
        bist_indicators = ['THYAO', 'GARAN', 'AKBNK', 'TUPRS', 'EREGL', 'ASELS', 
                          'KCHOL', 'SAHOL', 'FROTO', 'SISE', 'TOASO', 'BIMAS',
                          'MGROS', 'ARCLK', 'TCELL', 'TTKOM', 'VAKBN', 'YKBNK',
                          'HALKB', 'ISCTR', 'PETKM', 'KOZAL', 'KOZAA', 'EKGYO',
                          'ENKAI', 'TAVHL', 'DOHOL', 'GUBRF', 'KONTR', 'VESTL',
                          'SASA', 'SOKM', 'PGSUS', 'CCOLA', 'ULKER', 'AEFES',
                          'TTRAK', 'TKFEN', 'ODAS', 'OYAKC', 'CIMSA', 'TMSN',
                          'ENJSA', 'GESAN', 'BRSAN', 'ALARK', 'ISGYO', 'MPARK',
                          'LOGO', 'INDES', 'EGEEN', 'OTKAR', 'KLRHO', 'MAVI',
                          'NETAS', 'TURSG', 'AGHOL', 'QUAGR', 'VESBE', 'AKSA',
                          'ANACM', 'BUCIM', 'DOAS', 'YKBNK', 'KRDMD', 'IPEKE',
                          'YEOTK', 'POLHO', 'AKSEN', 'PEKGY', 'TSKB', 'ALBRK']
        
        # Bilinen ABD hisseleri (kısa kodlar)
        us_indicators = ['AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'TSLA', 
                        'NVDA', 'NFLX', 'AMD', 'INTC', 'UBER', 'PYPL', 'COIN',
                        'BA', 'DIS', 'BABA', 'NIO', 'PLTR', 'RIVN', 'LCID',
                        'SOFI', 'SNAP', 'PINS', 'ROKU', 'SQ', 'SHOP',
                        'ZM', 'HOOD', 'RBLX', 'U', 'ABNB', 'DKNG',
                        'V', 'MA', 'JPM', 'GS', 'MS', 'WMT', 'PG', 'KO', 'PEP',
                        'JNJ', 'UNH', 'XOM', 'CVX', 'SPY', 'QQQ', 'IWM',
                        'VTI', 'VOO', 'BRK', 'T', 'VZ', 'CSCO', 'CRM', 'ORCL',
                        'ADBE', 'AVGO', 'TXN', 'QCOM', 'MU', 'AMAT', 'LRCX',
                        'NOW', 'SNOW', 'NET', 'CRWD', 'ZS', 'PANW', 'DDOG',
                        'MDB', 'TEAM', 'WDAY', 'OKTA', 'TWLO', 'TTD', 'MELI']
        
        # Önce bilinen BIST listesinde ara
        if ticker in bist_indicators:
            return f"{ticker}.IS"
        
        # Bilinen ABD listesinde ara
        if ticker in us_indicators:
            return ticker
        
        # Bilinmeyen ticker - varsayılan olarak BIST dene (fetch_stock_live fallback yapacak)
        if len(ticker) <= 5 and ticker.isalpha():
            return f"{ticker}.IS"
        
        return ticker


def fetch_stock_live(ticker: str, period: str = "1y") -> Tuple[Optional[pd.DataFrame], str]:
    """
    Herhangi bir hissenin verilerini canlı olarak çeker.
    
    Returns:
        (DataFrame veya None, hata mesajı veya "")
    """
    normalized = normalize_ticker(ticker)
    
    try:
        stock = yf.Ticker(normalized)
        df = stock.history(period=period)
        
        if df.empty:
            # BIST olarak denemediyse .IS ile dene
            if not normalized.endswith('.IS'):
                normalized_bist = f"{ticker.upper()}.IS"
                stock = yf.Ticker(normalized_bist)
                df = stock.history(period=period)
                if not df.empty:
                    normalized = normalized_bist
            else:
                # .IS ile denedik başarısız oldu, düz ticker'ı dene (ABD hissesi olabilir)
                plain_ticker = ticker.upper().strip()
                stock = yf.Ticker(plain_ticker)
                df = stock.history(period=period)
                if not df.empty:
                    normalized = plain_ticker
        
        if df.empty:
            return None, f"'{ticker}' için veri bulunamadı. Hisse kodu doğru mu?"
        
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        df['Ticker'] = normalized
        
        return df, ""
    
    except Exception as e:
        return None, f"Veri çekilemedi: {str(e)}"


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Teknik indikatörleri ekler."""
    if df.empty or len(df) < 14:
        return df
    
    # RSI (14 günlük)
    df['RSI'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
    
    # MACD
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    # Hareketli Ortalamalar
    df['SMA_20'] = ta.trend.SMAIndicator(close=df['Close'], window=20).sma_indicator()
    df['SMA_50'] = ta.trend.SMAIndicator(close=df['Close'], window=50).sma_indicator()
    df['EMA_12'] = ta.trend.EMAIndicator(close=df['Close'], window=12).ema_indicator()
    df['EMA_26'] = ta.trend.EMAIndicator(close=df['Close'], window=26).ema_indicator()
    
    # Bollinger Bands
    bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20)
    df['BB_High'] = bollinger.bollinger_hband()
    df['BB_Low'] = bollinger.bollinger_lband()
    df['BB_Mid'] = bollinger.bollinger_mavg()
    
    # Stochastic
    stoch = ta.momentum.StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'])
    df['Stoch_K'] = stoch.stoch()
    df['Stoch_D'] = stoch.stoch_signal()
    
    # ATR (Volatilite)
    df['ATR'] = ta.volatility.AverageTrueRange(
        high=df['High'], low=df['Low'], close=df['Close']
    ).average_true_range()
    
    return df


def analyze_stock(ticker: str, period: str = "1y") -> Dict:
    """
    Tek bir hisseyi tam analiz eder.
    
    Returns:
        Dict with all analysis results
    """
    df, error = fetch_stock_live(ticker, period)
    
    if error:
        return {
            'success': False,
            'error': error,
            'ticker': ticker
        }
    
    # İndikatörleri ekle
    df = add_technical_indicators(df)
    
    # Son değerler
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    
    # Fiyat değişimi (günlük)
    price_change = last['Close'] - prev['Close']
    price_change_pct = (price_change / prev['Close']) * 100 if prev['Close'] else 0
    
    # 1 günlük getiri
    change_1d = price_change_pct
    
    # 1 haftalık getiri (~5 işlem günü)
    week_idx = max(0, len(df) - 6)
    week_price = df.iloc[week_idx]['Close']
    change_1w = ((last['Close'] - week_price) / week_price) * 100 if week_price else 0
    
    # 1 aylık getiri (~22 işlem günü)
    month_ago_idx = max(0, len(df) - 22)
    month_ago_price = df.iloc[month_ago_idx]['Close']
    monthly_return = ((last['Close'] - month_ago_price) / month_ago_price) * 100
    change_1m = monthly_return
    
    # 1 yıllık getiri
    yearly_return = ((last['Close'] - df.iloc[0]['Close']) / df.iloc[0]['Close']) * 100
    
    # 52 hafta yüksek/düşük
    high_52w = df['High'].max()
    low_52w = df['Low'].min()
    
    # Ortalama hacim
    avg_volume = df['Volume'].tail(20).mean() if 'Volume' in df.columns else 0
    
    # Sinyal analizi
    signals = generate_signals(last)
    
    # Destek/Direnç seviyeleri
    support_resistance = calculate_support_resistance(df)
    
    return {
        'success': True,
        'ticker': last.get('Ticker', ticker),
        'original_ticker': ticker,
        'data': df,
        'current_price': last['Close'],
        'previous_close': prev['Close'],
        'price_change': price_change,
        'price_change_pct': price_change_pct,
        'change_1d': change_1d,
        'change_1w': change_1w,
        'change_1m': change_1m,
        'monthly_return': monthly_return,
        'yearly_return': yearly_return,
        'high_52w': high_52w,
        'low_52w': low_52w,
        'avg_volume': avg_volume,
        'volume': last.get('Volume', 0),
        'high': last['High'],
        'low': last['Low'],
        'open': last.get('Open', last['Close']),
        'rsi': last.get('RSI'),
        'macd': last.get('MACD'),
        'macd_signal': last.get('MACD_Signal'),
        'macd_hist': last.get('MACD_Hist'),
        'sma_20': last.get('SMA_20'),
        'sma_50': last.get('SMA_50'),
        'bb_high': last.get('BB_High'),
        'bb_low': last.get('BB_Low'),
        'stoch_k': last.get('Stoch_K'),
        'stoch_d': last.get('Stoch_D'),
        'atr': last.get('ATR'),
        'signals': signals,
        'support_resistance': support_resistance,
        'last_update': last['Date'].strftime('%Y-%m-%d') if 'Date' in last else datetime.now().strftime('%Y-%m-%d')
    }


def generate_signals(row: pd.Series) -> Dict:
    """RSI, MACD ve diğer indikatörlere göre sinyal üretir."""
    signals = {
        'overall': 'Hold',
        'strength': 'Nötr',
        'score': 0,
        'details': []
    }
    
    buy_score = 0
    sell_score = 0
    details = []
    
    # RSI Analizi
    rsi = row.get('RSI')
    if pd.notna(rsi):
        if rsi < 30:
            buy_score += 2
            details.append(f"🟢 RSI aşırı satım ({rsi:.1f})")
        elif rsi < 40:
            buy_score += 1
            details.append(f"🟡 RSI düşük ({rsi:.1f})")
        elif rsi > 70:
            sell_score += 2
            details.append(f"🔴 RSI aşırı alım ({rsi:.1f})")
        elif rsi > 60:
            sell_score += 1
            details.append(f"🟡 RSI yüksek ({rsi:.1f})")
        else:
            details.append(f"⚪ RSI nötr ({rsi:.1f})")
    
    # MACD Analizi
    macd_hist = row.get('MACD_Hist')
    if pd.notna(macd_hist):
        if macd_hist > 0:
            buy_score += 1
            details.append("🟢 MACD pozitif momentum")
        else:
            sell_score += 1
            details.append("🔴 MACD negatif momentum")
    
    # Hareketli Ortalama Analizi
    close = row.get('Close')
    sma_20 = row.get('SMA_20')
    sma_50 = row.get('SMA_50')
    
    if pd.notna(close) and pd.notna(sma_20):
        if close > sma_20:
            buy_score += 1
            details.append("🟢 Fiyat 20 günlük ortalamanın üstünde")
        else:
            sell_score += 1
            details.append("🔴 Fiyat 20 günlük ortalamanın altında")
    
    if pd.notna(sma_20) and pd.notna(sma_50):
        if sma_20 > sma_50:
            buy_score += 1
            details.append("🟢 Golden Cross (SMA20 > SMA50)")
        else:
            sell_score += 1
            details.append("🔴 Death Cross (SMA20 < SMA50)")
    
    # Stochastic
    stoch_k = row.get('Stoch_K')
    if pd.notna(stoch_k):
        if stoch_k < 20:
            buy_score += 1
            details.append(f"🟢 Stochastic aşırı satım ({stoch_k:.1f})")
        elif stoch_k > 80:
            sell_score += 1
            details.append(f"🔴 Stochastic aşırı alım ({stoch_k:.1f})")
    
    # Bollinger Band
    bb_low = row.get('BB_Low')
    bb_high = row.get('BB_High')
    if pd.notna(close) and pd.notna(bb_low) and pd.notna(bb_high):
        if close <= bb_low:
            buy_score += 1
            details.append("🟢 Fiyat alt Bollinger bandında")
        elif close >= bb_high:
            sell_score += 1
            details.append("🔴 Fiyat üst Bollinger bandında")
    
    # Genel sinyal
    net_score = buy_score - sell_score
    
    if net_score >= 4:
        signals['overall'] = 'Güçlü Al'
        signals['strength'] = 'Güçlü'
    elif net_score >= 2:
        signals['overall'] = 'Al'
        signals['strength'] = 'Orta'
    elif net_score <= -4:
        signals['overall'] = 'Güçlü Sat'
        signals['strength'] = 'Güçlü'
    elif net_score <= -2:
        signals['overall'] = 'Sat'
        signals['strength'] = 'Orta'
    else:
        signals['overall'] = 'Tut'
        signals['strength'] = 'Zayıf'
    
    signals['score'] = net_score
    signals['buy_score'] = buy_score
    signals['sell_score'] = sell_score
    signals['details'] = details
    
    return signals


def calculate_support_resistance(df: pd.DataFrame, periods: int = 20) -> Dict:
    """Basit destek ve direnç seviyelerini hesaplar."""
    if len(df) < periods:
        return {'support': None, 'resistance': None}
    
    recent = df.tail(periods)
    
    return {
        'support': recent['Low'].min(),
        'resistance': recent['High'].max(),
        'pivot': (recent['High'].max() + recent['Low'].min() + recent['Close'].iloc[-1]) / 3
    }


def search_stocks(query: str) -> list:
    """
    Gelişmiş hisse arama fonksiyonu.
    Ticker kodu veya şirket adına göre arama yapar.
    Türkçe karakter desteği ile fuzzy matching.
    """
    # Geniş BIST hisse sözlüğü
    bist_stocks = {
        # Bankalar
        'GARAN': 'Garanti BBVA Bankası', 'AKBNK': 'Akbank', 'VAKBN': 'Vakıfbank',
        'YKBNK': 'Yapı Kredi Bankası', 'HALKB': 'Halkbank', 'ISCTR': 'İş Bankası',
        'TSKB': 'TSKB', 'ALBRK': 'Albaraka Türk', 'SKBNK': 'Şekerbank',
        'DENIZ': 'Denizbank', 'QNBFB': 'QNB Finansbank', 'ICBCT': 'ICBC Turkey',
        # Holding
        'KCHOL': 'Koç Holding', 'SAHOL': 'Sabancı Holding', 'DOHOL': 'Doğan Holding',
        'AGHOL': 'AG Anadolu Grubu Holding', 'TAVHL': 'TAV Havalimanları Holding',
        'TKFEN': 'Tekfen Holding', 'ECZYT': 'Eczacıbaşı Yatırım',
        # Havacılık ve Savunma
        'THYAO': 'Türk Hava Yolları', 'PGSUS': 'Pegasus', 'ASELS': 'Aselsan',
        'TUSAS': 'TUSAŞ Türk Havacılık ve Uzay', 'HRGYO': 'Hürriyet GYO',
        # Otomotiv
        'FROTO': 'Ford Otosan', 'TOASO': 'Tofaş', 'DOAS': 'Doğuş Otomotiv',
        'OTKAR': 'Otokar', 'TTRAK': 'Türk Traktör',
        # Perakende ve Gıda
        'BIMAS': 'BİM Mağazaları', 'MGROS': 'Migros Ticaret', 'SOKM': 'Şok Marketler',
        'CCOLA': 'Coca Cola İçecek', 'ULKER': 'Ülker Bisküvi', 'AEFES': 'Anadolu Efes',
        'BANVT': 'Banvit', 'KERVT': 'Kerevitaş', 'PETUN': 'Pınar Et ve Un',
        'PINSU': 'Pınar Su', 'PNSUT': 'Pınar Süt', 'TATGD': 'Tat Gıda',
        # Enerji ve Petrokimya
        'TUPRS': 'Tüpraş', 'PETKM': 'Petkim', 'AKSEN': 'Aksa Enerji',
        'ENJSA': 'Enerjisa', 'ODAS': 'Odaş Elektrik', 'AKFGY': 'Akfen GYO',
        'AYEN': 'Aydem Yenilenebilir Enerji', 'ENERY': 'Borusan EnBW Enerji',
        'ZOREN': 'Zorlu Enerji', 'GESAN': 'Giresun Sanayi',
        # Demir Çelik ve Madencilik
        'EREGL': 'Ereğli Demir ve Çelik', 'KRDMD': 'Kardemir', 'KOZAL': 'Koza Altın',
        'KOZAA': 'Koza Anadolu Metal', 'IPEKE': 'İpek Doğal Enerji',
        # Telekomünikasyon ve Teknoloji
        'TCELL': 'Turkcell', 'TTKOM': 'Türk Telekom', 'LOGO': 'Logo Yazılım',
        'INDES': 'İndeks Bilgisayar', 'NETAS': 'Netaş Telekomünikasyon',
        'ARENA': 'Arena Bilgisayar', 'ARDYZ': 'Ard Grup Bilişim',
        'ALCTL': 'Alcatel Lucent Teletaş', 'KFEIN': 'Kafein Yazılım',
        'PAPIL': 'Papilon Savunma', 'SMART': 'Smartiks Yazılım',
        # Sanayi ve Üretim
        'SISE': 'Şişecam', 'ARCLK': 'Arçelik', 'VESTL': 'Vestel',
        'VESBE': 'Vestel Beyaz Eşya', 'SASA': 'SASA Polyester',
        'BRSAN': 'Borusan Mannesmann', 'ENKAI': 'Enka İnşaat',
        'ALARK': 'Alarko Holding', 'GUBRF': 'Gübre Fabrikaları',
        'KONTR': 'Kontrolmatik Teknoloji', 'EGEEN': 'Ege Endüstri',
        'ANACM': 'Anadolu Cam', 'BUCIM': 'Bursa Çimento', 'CIMSA': 'Çimsa',
        'AKSA': 'Aksa Akrilik', 'TMSN': 'Tümosan Motor',
        'POLHO': 'Polisan Holding', 'MAVI': 'Mavi Giyim',
        # GYO
        'EKGYO': 'Emlak Konut GYO', 'ISGYO': 'İş GYO', 'MPARK': 'MLP Saglik GYO',
        'PEKGY': 'Pera GYO', 'RYGYO': 'Reysaş GYO', 'HLGYO': 'Halk GYO',
        'YGGYO': 'Yeşil GYO', 'VKGYO': 'Vakıf GYO',
        # Sigorta
        'TURSG': 'Türkiye Sigorta', 'AGESA': 'AgeSA Hayat ve Emeklilik',
        'ANHYT': 'Anadolu Hayat Emeklilik', 'AKGRT': 'Aksigorta',
        # Diğer
        'QUAGR': 'QUA Granite', 'YEOTK': 'YEO Teknoloji', 'MPARK': 'MLP Saglik',
        'KLRHO': 'Kiler Holding', 'OYAKC': 'OYAK Çimento',
        'BIZIM': 'Bizim Toptan', 'CEMAS': 'Çemaş Döküm',
        'DYOBY': 'DYO Boya', 'GOODY': 'Goodyear', 'HEKTS': 'Hektaş',
        'ISMEN': 'İş Yatırım Menkul', 'KARSN': 'Karsan Otomotiv',
        'KENT': 'Kent Gıda', 'MNDRS': 'Menderes Tekstil',
        'PARSN': 'Parsan', 'SARKY': 'Sarkuysan', 'SILVR': 'Silverline Endüstri',
        'SMRTG': 'Smart Güneş Enerjisi', 'TRGYO': 'Torunlar GYO',
        'VERTU': 'Vertu Motorlu Araçlar', 'YATAS': 'Yataş',
        'BERA': 'Bera Holding', 'CANTE': 'Çan2 Termik', 'BTCIM': 'Batıçim',
        'GOLTS': 'Göltas Çimento', 'KCAER': 'Kocaer Çelik',
        'KTLEV': 'Katılım Emeklilik', 'MIATK': 'Mia Teknoloji',
        'PGENY': 'Pakel Geniş Enerji', 'SUNTK': 'Sun Tekstil',
        'TABLA': 'Tabal Holding', 'TKURU': 'Tüm Kuruyemiş',
    }
    
    # ABD hisseleri
    us_stocks = {
        'AAPL': 'Apple', 'MSFT': 'Microsoft', 'GOOGL': 'Alphabet (Google)',
        'AMZN': 'Amazon', 'META': 'Meta Platforms (Facebook)', 'TSLA': 'Tesla',
        'NVDA': 'NVIDIA', 'NFLX': 'Netflix', 'AMD': 'AMD',
        'INTC': 'Intel', 'UBER': 'Uber', 'PYPL': 'PayPal',
        'COIN': 'Coinbase', 'BA': 'Boeing', 'DIS': 'Walt Disney',
        'BABA': 'Alibaba', 'NIO': 'NIO', 'PLTR': 'Palantir',
        'V': 'Visa', 'MA': 'Mastercard', 'JPM': 'JP Morgan',
        'GS': 'Goldman Sachs', 'WMT': 'Walmart', 'KO': 'Coca Cola',
        'PEP': 'PepsiCo', 'SPY': 'S&P 500 ETF', 'QQQ': 'Nasdaq 100 ETF',
    }
    
    def _normalize_turkish(text: str) -> str:
        """Türkçe karakterleri ASCII'ye çevir (arama için)."""
        tr_map = str.maketrans('çÇğĞıİöÖşŞüÜâÂîÎûÛ', 'cCgGiIoOsSuUaAiIuU')
        return text.translate(tr_map).upper()
    
    query_clean = query.strip()
    query_upper = query_clean.upper()
    query_norm = _normalize_turkish(query_clean)
    
    results = []
    
    # BIST hisselerinde ara
    for code, name in bist_stocks.items():
        code_norm = _normalize_turkish(code)
        name_norm = _normalize_turkish(name)
        
        # Ticker kodu eşleşmesi (tam veya kısmi)
        ticker_match = (query_upper == code or query_upper in code or code.startswith(query_upper))
        
        # İsim eşleşmesi (Türkçe normalize)
        name_match = (query_norm in name_norm or 
                     any(word in name_norm for word in query_norm.split() if len(word) >= 2))
        
        if ticker_match or name_match:
            # Sıralama puanı: tam eşleşme > başlangıç eşleşmesi > kısmi eşleşme
            score = 0
            if query_upper == code:
                score = 100
            elif code.startswith(query_upper):
                score = 80
            elif query_upper in code:
                score = 60
            elif query_norm in name_norm:
                score = 40
            else:
                score = 20
            
            results.append({
                'ticker': code,
                'name': name,
                'market': 'BIST',
                '_score': score
            })
    
    # ABD hisselerinde ara
    for code, name in us_stocks.items():
        name_upper = name.upper()
        
        if query_upper == code or query_upper in code or code.startswith(query_upper):
            score = 100 if query_upper == code else (80 if code.startswith(query_upper) else 60)
            results.append({
                'ticker': code,
                'name': name,
                'market': 'US',
                '_score': score
            })
        elif query_norm in name_upper:
            results.append({
                'ticker': code,
                'name': name,
                'market': 'US',
                '_score': 30
            })
    
    # Puanlama sıralaması
    results.sort(key=lambda x: x['_score'], reverse=True)
    
    # _score alanını kaldır
    for r in results:
        r.pop('_score', None)
    
    # Eğer sonuç yoksa ve girdi BIST ticker formatındaysa, direkt dene
    if not results and len(query_clean) >= 2 and query_clean.isalpha():
        results.append({
            'ticker': query_upper,
            'name': f'{query_upper} (Doğrudan arama)',
            'market': 'BIST' if len(query_upper) <= 5 else 'US'
        })
    
    return results[:15]  # İlk 15 sonuç


def compare_stocks(tickers: list, period: str = "1mo") -> pd.DataFrame:
    """Birden fazla hisseyi karşılaştırır."""
    results = []
    
    for ticker in tickers:
        analysis = analyze_stock(ticker, period)
        if analysis['success']:
            results.append({
                'Hisse': analysis['ticker'],
                'Fiyat': analysis['current_price'],
                'Günlük %': analysis['price_change_pct'],
                'Aylık %': analysis['monthly_return'],
                'RSI': analysis['rsi'],
                'Sinyal': analysis['signals']['overall']
            })
    
    return pd.DataFrame(results)


if __name__ == '__main__':
    # Test
    print("=" * 60)
    print("🔍 Dinamik Hisse Analizi Testi")
    print("=" * 60)
    
    test_tickers = ['THYAO', 'AAPL', 'ASELS']
    
    for ticker in test_tickers:
        print(f"\n📈 {ticker} analiz ediliyor...")
        result = analyze_stock(ticker)
        
        if result['success']:
            print(f"  Fiyat: {result['current_price']:.2f}")
            print(f"  Günlük: {result['price_change_pct']:+.2f}%")
            print(f"  Aylık: {result['monthly_return']:+.2f}%")
            print(f"  RSI: {result['rsi']:.1f}" if result['rsi'] else "  RSI: N/A")
            print(f"  Sinyal: {result['signals']['overall']}")
        else:
            print(f"  ❌ {result['error']}")
