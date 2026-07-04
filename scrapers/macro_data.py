"""
Makro Ekonomik Veri ve Borsa API'leri
- yfinance: Borsa verileri (THYAO, AAPL vb.)
- Technical Analysis (ta): RSI, MACD indikatörleri
- Enflasyon verileri (TÜİK, FED)
"""

import sys
import os
import pandas as pd
import yfinance as yf
import ta
from datetime import datetime, timedelta

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import insert_stock_data, insert_macro_data, get_connection


# Takip edilecek hisseler
TICKERS = {
    "TR": ["THYAO.IS", "GARAN.IS", "AKBNK.IS", "TUPRS.IS", "EREGL.IS"],  # Borsa İstanbul
    "US": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]  # ABD Hisseleri
}


def fetch_stock_data(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    yfinance kullanarak hisse verisi çeker.
    
    Args:
        ticker: Hisse kodu (örn: "THYAO.IS", "AAPL")
        period: Süre (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        
        if df.empty:
            print(f"⚠️ {ticker} için veri bulunamadı")
            return pd.DataFrame()
        
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        
        return df
    except Exception as e:
        print(f"❌ {ticker} verisi çekilemedi: {e}")
        return pd.DataFrame()


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame'e teknik indikatörler ekler.
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - SMA (Simple Moving Average)
    - Bollinger Bands
    """
    if df.empty:
        return df
    
    # RSI (14 günlük)
    df['RSI'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
    
    # MACD
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Diff'] = macd.macd_diff()
    
    # SMA (20 ve 50 günlük)
    df['SMA_20'] = ta.trend.SMAIndicator(close=df['Close'], window=20).sma_indicator()
    df['SMA_50'] = ta.trend.SMAIndicator(close=df['Close'], window=50).sma_indicator()
    
    # Bollinger Bands
    bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20)
    df['BB_High'] = bollinger.bollinger_hband()
    df['BB_Low'] = bollinger.bollinger_lband()
    df['BB_Mid'] = bollinger.bollinger_mavg()
    
    return df


def generate_signal(row: pd.Series) -> str:
    """
    RSI ve MACD'ye göre basit sinyal üretir.
    """
    rsi = row.get('RSI')
    macd_diff = row.get('MACD_Diff')
    
    if pd.isna(rsi) or pd.isna(macd_diff):
        return "Hold"
    
    # RSI bazlı sinyal
    if rsi < 30:
        rsi_signal = "Buy"
    elif rsi > 70:
        rsi_signal = "Sell"
    else:
        rsi_signal = "Hold"
    
    # MACD bazlı sinyal
    if macd_diff > 0:
        macd_signal = "Buy"
    else:
        macd_signal = "Sell"
    
    # Kombine sinyal
    if rsi_signal == "Buy" and macd_signal == "Buy":
        return "Strong Buy"
    elif rsi_signal == "Sell" and macd_signal == "Sell":
        return "Strong Sell"
    elif rsi_signal == "Buy" or macd_signal == "Buy":
        return "Buy"
    elif rsi_signal == "Sell" or macd_signal == "Sell":
        return "Sell"
    else:
        return "Hold"


def fetch_and_save_stock(ticker: str, period: str = "1y"):
    """
    Hisse verisini çeker, indikatör ekler ve veritabanına kaydeder.
    """
    print(f"📈 {ticker} verisi çekiliyor...")
    
    df = fetch_stock_data(ticker, period)
    
    if df.empty:
        return False
    
    df = add_technical_indicators(df)
    
    # Veritabanına kaydet
    saved_count = 0
    for _, row in df.iterrows():
        signal = generate_signal(row)
        
        insert_stock_data(
            ticker=ticker,
            date=str(row['Date']),
            open_price=row.get('Open'),
            high_price=row.get('High'),
            low_price=row.get('Low'),
            close_price=row['Close'],
            volume=row.get('Volume'),
            rsi_value=row.get('RSI'),
            macd_value=row.get('MACD'),
            macd_signal=row.get('MACD_Signal'),
            signal=signal
        )
        saved_count += 1
    
    print(f"  ✅ {saved_count} kayıt veritabanına eklendi")
    return True


def fetch_all_stocks():
    """Tüm takip edilen hisseleri çeker."""
    print("=" * 50)
    print("📊 Borsa Verileri Çekiliyor...")
    print("=" * 50)
    
    success_count = 0
    total_count = 0
    
    for country, tickers in TICKERS.items():
        print(f"\n🌍 {country} Hisseleri:")
        for ticker in tickers:
            total_count += 1
            if fetch_and_save_stock(ticker):
                success_count += 1
    
    print(f"\n📊 Toplam: {success_count}/{total_count} hisse başarıyla kaydedildi")
    return success_count


def fetch_macro_data():
    """
    Makro ekonomik verileri çeker.
    Not: Gerçek API'ler (EVDS, FRED) için API key gerekir.
    Burada örnek/simüle veri üretiyoruz.
    """
    print("\n" + "=" * 50)
    print("📉 Makro Ekonomik Veriler Çekiliyor...")
    print("=" * 50)
    
    # Örnek enflasyon verileri (Gerçek kullanımda API'lerden çekilmeli)
    sample_macro_data = [
        # Türkiye
        {"date": "2025-12-01", "country": "TR", "data_type": "CPI", "value": 48.52},
        {"date": "2025-11-01", "country": "TR", "data_type": "CPI", "value": 47.09},
        {"date": "2025-10-01", "country": "TR", "data_type": "CPI", "value": 48.58},
        {"date": "2025-12-01", "country": "TR", "data_type": "Interest", "value": 45.00},
        {"date": "2025-11-01", "country": "TR", "data_type": "Interest", "value": 47.50},
        
        # ABD
        {"date": "2025-12-01", "country": "US", "data_type": "CPI", "value": 2.9},
        {"date": "2025-11-01", "country": "US", "data_type": "CPI", "value": 2.7},
        {"date": "2025-10-01", "country": "US", "data_type": "CPI", "value": 2.6},
        {"date": "2025-12-01", "country": "US", "data_type": "Interest", "value": 4.50},
        {"date": "2025-11-01", "country": "US", "data_type": "Interest", "value": 4.75},
    ]
    
    for data in sample_macro_data:
        insert_macro_data(
            date=data["date"],
            country=data["country"],
            data_type=data["data_type"],
            value=data["value"]
        )
    
    print(f"✅ {len(sample_macro_data)} makro veri kaydedildi")
    
    # FRED API kullanımı örneği (API key gerektirir)
    """
    from fredapi import Fred
    fred = Fred(api_key='YOUR_API_KEY')
    
    # ABD CPI verisi
    cpi_data = fred.get_series('CPIAUCSL')
    """
    
    return len(sample_macro_data)


def get_latest_stock_data(ticker: str = None) -> pd.DataFrame:
    """Veritabanından en son hisse verilerini getirir."""
    conn = get_connection()
    
    if ticker:
        query = """
            SELECT * FROM stocks 
            WHERE ticker = ? 
            ORDER BY date DESC 
            LIMIT 100
        """
        df = pd.read_sql_query(query, conn, params=(ticker,))
    else:
        query = """
            SELECT * FROM stocks 
            ORDER BY date DESC, ticker 
            LIMIT 500
        """
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    return df


def get_stock_summary() -> pd.DataFrame:
    """Her hisse için son durum özeti döndürür."""
    conn = get_connection()
    
    query = """
        SELECT 
            ticker,
            MAX(date) as last_date,
            (SELECT close_price FROM stocks s2 
             WHERE s2.ticker = stocks.ticker 
             ORDER BY date DESC LIMIT 1) as last_price,
            (SELECT rsi_value FROM stocks s3 
             WHERE s3.ticker = stocks.ticker 
             ORDER BY date DESC LIMIT 1) as last_rsi,
            (SELECT signal FROM stocks s4 
             WHERE s4.ticker = stocks.ticker 
             ORDER BY date DESC LIMIT 1) as last_signal
        FROM stocks
        GROUP BY ticker
        ORDER BY ticker
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


if __name__ == '__main__':
    # Veritabanını başlat
    from database import init_database
    init_database()
    
    # Tüm verileri çek
    fetch_all_stocks()
    fetch_macro_data()
    
    # Özet göster
    print("\n" + "=" * 50)
    print("📊 Hisse Özeti:")
    print("=" * 50)
    summary = get_stock_summary()
    print(summary.to_string(index=False))
