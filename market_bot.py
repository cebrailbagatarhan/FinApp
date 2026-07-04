"""
Market Bot - Otomatik Günlük Fiyat Tarayıcı
CSV'den ürün listesini okur ve Migros'tan fiyatları çeker.
Her sabah 09:00'da otomatik çalışır.
"""

import csv
import time
import random
import sys
import os
import schedule
from datetime import datetime

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

from database import init_database, insert_product, get_connection

# Smart Scraper (Selenium yerine Requests + BeautifulSoup)
try:
    from scrapers.smart_scraper import SmartScraper
    SMART_SCRAPER_AVAILABLE = True
except ImportError:
    SMART_SCRAPER_AVAILABLE = False

# Dosya yolları
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'urunler.csv')
LOG_FILE = os.path.join(BASE_DIR, 'data', 'bot_log.txt')


def log_message(message: str):
    """Log dosyasına mesaj yazar."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry + '\n')


def get_chrome_driver():
    """Anti-bot önlemli Chrome driver oluşturur."""
    ua = UserAgent()
    user_agent = ua.random
    
    options = Options()
    options.add_argument(f'user-agent={user_agent}')
    options.add_argument('--headless=new')  # Yeni headless modu
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Proxy kullanmak istersen buraya ekleyebilirsin
    # options.add_argument('--proxy-server=http://proxy:port')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Bot tespitini zorlaştır
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR', 'tr', 'en-US', 'en']});
        '''
    })
    
    return driver


def read_products_from_csv() -> list:
    """CSV dosyasından ürün listesini okur."""
    products = []
    
    if not os.path.exists(CSV_FILE):
        log_message(f"❌ CSV dosyası bulunamadı: {CSV_FILE}")
        return products
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append({
                    'name': row.get('Ürün Adı', '').strip(),
                    'url': row.get('Migros_Link', '').strip(),
                    'category': row.get('Kategori', 'Diğer').strip()
                })
        
        log_message(f"📋 CSV'den {len(products)} ürün okundu")
    except Exception as e:
        log_message(f"❌ CSV okuma hatası: {e}")
    
    return products


def scrape_migros_price(driver, url: str, product_name: str) -> float:
    """Migros'tan tek bir ürünün fiyatını çeker."""
    try:
        driver.get(url)
        
        # Rastgele bekleme (bot tespitini zorlaştırır)
        time.sleep(random.uniform(2, 5))
        
        # Farklı CSS seçicilerini dene (Migros yapısı değişebilir)
        price_selectors = [
            # Migros'un olası fiyat elementleri
            '[data-monitor-name="productPrice"]',
            '.price-new',
            '.product-price-new',
            '.price',
            'span[class*="price"]',
            'div[class*="Price"] span',
            '.money-integer',
            '[class*="ProductPrice"]',
            '.jsx-price',
        ]
        
        for selector in price_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    price_text = element.text.strip()
                    if price_text and any(c.isdigit() for c in price_text):
                        # Fiyatı parse et
                        price = parse_price(price_text)
                        if price and price > 0:
                            return price
            except:
                continue
        
        # JavaScript ile fiyat aramayı dene
        try:
            price_js = driver.execute_script('''
                var prices = document.querySelectorAll('[class*="price"], [class*="Price"]');
                for (var i = 0; i < prices.length; i++) {
                    var text = prices[i].innerText;
                    if (text && text.match(/\\d+[,.]\\d{2}/)) {
                        return text;
                    }
                }
                return null;
            ''')
            if price_js:
                return parse_price(price_js)
        except:
            pass
        
        log_message(f"⚠️ Fiyat bulunamadı: {product_name}")
        return None
        
    except Exception as e:
        log_message(f"❌ Scraping hatası ({product_name}): {e}")
        return None


def parse_price(price_text: str) -> float:
    """Fiyat metnini float'a çevirir."""
    try:
        # Temizle: ₺, TL, boşluk vs.
        cleaned = price_text.replace('₺', '').replace('TL', '')
        cleaned = cleaned.replace(' ', '').strip()
        
        # Türkçe format: 1.234,56 -> 1234.56
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        
        # Sadece sayısal karakterleri al
        import re
        match = re.search(r'(\d+\.?\d*)', cleaned)
        if match:
            return float(match.group(1))
        
        return None
    except:
        return None


def scrape_all_products_smart():
    """
    YENI: Smart Scraper ile tüm ürünleri tarar.
    Reverse Engineering tabanlı - Selenium yerine Requests kullanır.
    
    Öncelik sırası:
    1. Schema.org JSON-LD (en güvenilir)
    2. Next.js __NEXT_DATA__
    3. Gömülü JavaScript JSON
    4. HTML CSS Selector (son çare)
    """
    log_message("=" * 50)
    log_message("🧠 SMART SCRAPER Başlatıldı (Reverse Engineering)")
    log_message("=" * 50)
    
    init_database()
    products = read_products_from_csv()
    
    if not products:
        log_message("❌ Taranacak ürün bulunamadı!")
        return 0
    
    scraper = SmartScraper()
    success_count = 0
    fail_count = 0
    today = datetime.now().strftime('%Y-%m-%d')
    
    for i, product in enumerate(products, 1):
        name = product['name']
        url = product['url']
        category = product['category']
        
        log_message(f"[{i}/{len(products)}] 🔍 {name}")
        
        if not url or not url.startswith('http'):
            log_message(f"  ⚠️ Geçersiz URL, atlanıyor")
            fail_count += 1
            continue
        
        result = scraper.scrape(url, expected_name=name)
        
        if result and result.price > 0:
            # Veritabanına kaydet (category ile birlikte)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO products (market_name, product_name, price, currency, category, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('Migros', name, result.price, result.currency, category, today))
            conn.commit()
            conn.close()
            
            log_message(f"  ✅ {result.price:.2f} TL (kaynak: {result.source})")
            success_count += 1
        else:
            log_message(f"  ❌ Fiyat bulunamadı")
            fail_count += 1
        
        # Rate limiting
        if i < len(products):
            time.sleep(random.uniform(2, 4))
    
    log_message("=" * 50)
    log_message(f"📊 Sonuç: {success_count} başarılı, {fail_count} başarısız")
    scraper.print_stats()
    log_message("=" * 50)
    
    return success_count


def scrape_all_products():
    """
    Tüm ürünleri tarar ve veritabanına kaydeder.
    
    Eğer SmartScraper mevcutsa onu kullanır (hızlı, hafif),
    değilse Selenium'a geri döner.
    """
    # Önce Smart Scraper'i dene
    if SMART_SCRAPER_AVAILABLE:
        try:
            return scrape_all_products_smart()
        except Exception as e:
            log_message(f"⚠️ Smart Scraper hatası, Selenium'a geçiliyor: {e}")
    
    # Fallback: Selenium
    return scrape_all_products_selenium()


def scrape_all_products_selenium():
    """Selenium ile tüm ürünleri tarar (eski yöntem)."""
    log_message("=" * 50)
    log_message("🚀 Market Bot Başlatıldı (Selenium)")
    log_message("=" * 50)
    
    # Veritabanını başlat
    init_database()
    
    # Ürünleri oku
    products = read_products_from_csv()
    
    if not products:
        log_message("❌ Taranacak ürün bulunamadı!")
        return 0
    
    driver = None
    success_count = 0
    fail_count = 0
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        driver = get_chrome_driver()
        log_message("✅ Chrome driver başlatıldı")
        
        for i, product in enumerate(products, 1):
            name = product['name']
            url = product['url']
            category = product['category']
            
            log_message(f"[{i}/{len(products)}] 🔍 {name} taranıyor...")
            
            if not url or not url.startswith('http'):
                log_message(f"  ⚠️ Geçersiz URL, atlanıyor")
                fail_count += 1
                continue
            
            price = scrape_migros_price(driver, url, name)
            
            if price:
                # Veritabanına kaydet (category ile birlikte)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO products (market_name, product_name, price, currency, category, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('Migros', name, price, 'TRY', category, today))
                conn.commit()
                conn.close()
                
                log_message(f"  ✅ {name}: {price:.2f} TL")
                success_count += 1
            else:
                fail_count += 1
            
            # Her ürün arasında rastgele bekleme
            if i < len(products):
                wait_time = random.uniform(3, 7)
                time.sleep(wait_time)
    
    except Exception as e:
        log_message(f"❌ Kritik hata: {e}")
    
    finally:
        if driver:
            driver.quit()
            log_message("🔒 Chrome driver kapatıldı")
    
    log_message("=" * 50)
    log_message(f"📊 Sonuç: {success_count} başarılı, {fail_count} başarısız")
    log_message("=" * 50)
    
    return success_count


def generate_sample_prices():
    """
    Gerçek scraping çalışmazsa örnek fiyat verileri üretir.
    Enflasyon simülasyonu ile gerçekçi fiyatlar.
    """
    log_message("📦 Örnek fiyat verileri üretiliyor...")
    
    init_database()
    products = read_products_from_csv()
    
    if not products:
        log_message("❌ CSV'de ürün yok!")
        return
    
    # Kategori bazlı baz fiyatlar (TL)
    base_prices = {
        "Süt (1L)": 42.90,
        "Yumurta (15'li)": 89.90,
        "Beyaz Peynir (600g)": 189.90,
        "Tereyağı (250g)": 129.90,
        "Ayçiçek Yağı (1L)": 109.90,
        "Zeytinyağı (1L)": 289.90,
        "Ekmek (Tam Buğday)": 24.90,
        "Un (2kg)": 54.90,
        "Şeker (1kg)": 44.90,
        "Pirinç Baldo (1kg)": 79.90,
        "Bulgur (1kg)": 39.90,
        "Makarna (500g)": 29.90,
        "Domates Salçası (700g)": 69.90,
        "Mercimek Kırmızı (1kg)": 89.90,
        "Nohut (1kg)": 79.90,
        "Tavuk Göğsü (kg)": 189.90,
        "Kıyma Dana (kg)": 449.90,
        "Çay (1kg)": 189.90,
        "Kahve (100g)": 149.90,
        "Deterjan (4kg)": 299.90,
        "Bulaşık Deterjanı (1L)": 89.90,
        "Tuvalet Kağıdı (32'li)": 299.90,
        "Diş Macunu": 79.90,
        "Patates (kg)": 29.90,
        "Soğan (kg)": 34.90,
        "Domates (kg)": 49.90,
        "Elma (kg)": 44.90,
        "Muz (kg)": 69.90,
        "Portakal (kg)": 39.90,
        "Limon (kg)": 49.90,
    }
    
    from datetime import timedelta
    today = datetime.now()
    
    # Son 30 gün için veri üret
    conn = get_connection()
    cursor = conn.cursor()
    
    for day_offset in range(30):
        current_date = (today - timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        for product in products:
            name = product['name']
            category = product.get('category', 'Diğer')
            
            # Baz fiyatı bul veya rastgele ata
            base_price = base_prices.get(name, random.uniform(20, 200))
            
            # Enflasyon faktörü (eskiye gittikçe fiyat düşer)
            inflation_factor = 1 - (day_offset * 0.002)  # Günlük ~%0.2 enflasyon
            
            # Rastgele varyans
            variance = random.uniform(-0.03, 0.03)  # ±%3 varyans
            
            price = base_price * inflation_factor * (1 + variance)
            
            # Category ile birlikte kaydet
            cursor.execute('''
                INSERT INTO products (market_name, product_name, price, currency, category, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('Migros', name, round(price, 2), 'TRY', category, current_date))
    
    conn.commit()
    conn.close()
    
    log_message(f"✅ {30} gün x {len(products)} ürün = {30 * len(products)} kayıt oluşturuldu!")


def run_daily_job():
    """Günlük tarama işi."""
    log_message("\n⏰ Zamanlanmış tarama başlıyor...")
    
    try:
        success = scrape_all_products()
        
        # Eğer hiç veri çekilemediyse örnek veri üret
        if success == 0:
            log_message("⚠️ Scraping başarısız, örnek veri üretiliyor...")
            generate_sample_prices()
    
    except Exception as e:
        log_message(f"❌ Günlük iş hatası: {e}")
        generate_sample_prices()


def start_scheduler():
    """Zamanlayıcıyı başlatır - Her sabah 09:00."""
    log_message("⏰ Zamanlayıcı başlatılıyor...")
    log_message("   Günlük tarama saati: 09:00")
    log_message("   Durdurmak için: Ctrl+C")
    
    # Her gün 09:00'da çalış
    schedule.every().day.at("09:00").do(run_daily_job)
    
    # Test için her 6 saatte bir de çalıştırabilirsin:
    # schedule.every(6).hours.do(run_daily_job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Her dakika kontrol et


def main():
    """Ana fonksiyon."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Market Fiyat Botu')
    parser.add_argument('--now', action='store_true', help='Hemen tarama yap')
    parser.add_argument('--sample', action='store_true', help='Örnek veri üret')
    parser.add_argument('--schedule', action='store_true', help='Zamanlayıcı modunda başlat')
    
    args = parser.parse_args()
    
    if args.sample:
        generate_sample_prices()
    elif args.now:
        run_daily_job()
    elif args.schedule:
        # İlk çalıştırmada hemen bir tarama yap
        run_daily_job()
        # Sonra zamanlayıcıyı başlat
        start_scheduler()
    else:
        # Varsayılan: Örnek veri üret (scraping hata verebilir)
        print("Kullanım:")
        print("  python market_bot.py --now       # Hemen tarama yap")
        print("  python market_bot.py --sample    # Örnek veri üret")
        print("  python market_bot.py --schedule  # Zamanlayıcı modunda başlat")
        print("\nÖrnek veri üretiliyor...")
        generate_sample_prices()


if __name__ == '__main__':
    main()
