"""
FinApp Başlatıcı
Dashboard'u kolay başlatmak için kullanın.
"""

import subprocess
import sys
import os

def main():
    # Çalışma dizinini ayarla
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)
    
    print("=" * 50)
    print("🚀 FinApp Başlatılıyor...")
    print("=" * 50)
    
    # Veritabanını kontrol et
    from database import init_database, get_connection
    init_database()
    
    # Veri var mı kontrol et
    conn = get_connection()
    import sqlite3
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stocks")
    stock_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products")
    product_count = cursor.fetchone()[0]
    conn.close()
    
    if stock_count == 0:
        print("\n📊 Hisse verisi bulunamadı. Veriler çekiliyor...")
        from scrapers.macro_data import fetch_all_stocks, fetch_macro_data
        fetch_all_stocks()
        fetch_macro_data()
    
    if product_count == 0:
        print("\n🛒 Market verisi bulunamadı. Örnek veri üretiliyor...")
        from scrapers.market_scraper import generate_sample_data
        generate_sample_data(days=30)
    
    print("\n✅ Veriler hazır!")
    print("\n🌐 Dashboard açılıyor...")
    print("   URL: http://localhost:8501")
    print("\n   Durdurmak için: Ctrl+C")
    print("=" * 50)
    
    # Streamlit'i başlat
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])


if __name__ == '__main__':
    main()
