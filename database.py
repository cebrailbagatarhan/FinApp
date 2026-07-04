"""
Veritabanı Kurulum Scripti
SQLite veritabanı oluşturur ve gerekli tabloları yaratır.
"""

import sqlite3
import os
from datetime import datetime

# Veritabanı dosya yolu
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'finapp.db')


def get_connection():
    """Veritabanı bağlantısı döndürür."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Veritabanı tablolarını oluşturur."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Products tablosu - Market fiyatları için
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT DEFAULT 'TRY',
            category TEXT DEFAULT 'Diğer',
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Mevcut tabloya category sütunu ekle (varsa görmezden gel)
    try:
        cursor.execute('ALTER TABLE products ADD COLUMN category TEXT DEFAULT "Diğer"')
    except sqlite3.OperationalError:
        pass  # Sütun zaten var
    
    # Macro Data tablosu - Enflasyon, faiz gibi makro veriler
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS macro_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            country TEXT NOT NULL,
            data_type TEXT NOT NULL,
            value REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, country, data_type)
        )
    ''')
    
    # Stocks tablosu - Hisse senedi verileri
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date DATE NOT NULL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL NOT NULL,
            volume INTEGER,
            rsi_value REAL,
            macd_value REAL,
            macd_signal REAL,
            signal TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, date)
        )
    ''')
    
    # Signals tablosu - Al/Sat sinyalleri için ayrı tablo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            signal_strength TEXT NOT NULL,
            reason TEXT,
            price_at_signal REAL,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Veritabanı başarıyla oluşturuldu!")
    print(f"📁 Konum: {DB_PATH}")


def insert_product(market_name: str, product_name: str, price: float, currency: str = 'TRY', date: str = None):
    """Ürün fiyatı ekler."""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (market_name, product_name, price, currency, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (market_name, product_name, price, currency, date))
    conn.commit()
    conn.close()


def insert_macro_data(date: str, country: str, data_type: str, value: float):
    """Makro ekonomik veri ekler."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO macro_data (date, country, data_type, value)
        VALUES (?, ?, ?, ?)
    ''', (date, country, data_type, value))
    conn.commit()
    conn.close()


def insert_stock_data(ticker: str, date: str, close_price: float, 
                      open_price: float = None, high_price: float = None,
                      low_price: float = None, volume: int = None,
                      rsi_value: float = None, macd_value: float = None,
                      macd_signal: float = None, signal: str = None):
    """Hisse senedi verisi ekler."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO stocks 
        (ticker, date, open_price, high_price, low_price, close_price, 
         volume, rsi_value, macd_value, macd_signal, signal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticker, date, open_price, high_price, low_price, close_price,
          volume, rsi_value, macd_value, macd_signal, signal))
    conn.commit()
    conn.close()


def insert_signal(ticker: str, signal_type: str, signal_strength: str, 
                  reason: str, price_at_signal: float, date: str = None):
    """Al/Sat sinyali ekler."""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO signals (ticker, signal_type, signal_strength, reason, price_at_signal, date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (ticker, signal_type, signal_strength, reason, price_at_signal, date))
    conn.commit()
    conn.close()


def get_all_products(market_name: str = None, days: int = 30):
    """Ürünleri getirir."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if market_name:
        cursor.execute('''
            SELECT * FROM products 
            WHERE market_name = ? AND date >= date('now', ?)
            ORDER BY date DESC
        ''', (market_name, f'-{days} days'))
    else:
        cursor.execute('''
            SELECT * FROM products 
            WHERE date >= date('now', ?)
            ORDER BY date DESC
        ''', (f'-{days} days',))
    
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]


def get_stock_data(ticker: str = None, days: int = 365):
    """Hisse verilerini getirir."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if ticker:
        cursor.execute('''
            SELECT * FROM stocks 
            WHERE ticker = ? AND date >= date('now', ?)
            ORDER BY date DESC
        ''', (ticker, f'-{days} days'))
    else:
        cursor.execute('''
            SELECT * FROM stocks 
            WHERE date >= date('now', ?)
            ORDER BY date DESC
        ''', (f'-{days} days',))
    
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]


def get_signals(days: int = 30):
    """Son sinyalleri getirir."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM signals 
        WHERE date >= date('now', ?)
        ORDER BY date DESC, created_at DESC
    ''', (f'-{days} days',))
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]


if __name__ == '__main__':
    init_database()
