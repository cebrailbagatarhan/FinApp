"""
Market Scraper - Süpermarket Fiyat Kazıyıcı
Migros ve benzeri marketlerden ürün fiyatlarını çeker.
"""

import time
import random
import sys
import os

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from datetime import datetime
from database import insert_product


# Takip edilecek ürünler ve URL'leri
MIGROS_PRODUCTS = {
    "Süt (1L)": "https://www.migros.com.tr/sut-1-l-p-",
    "Yumurta (15'li)": "https://www.migros.com.tr/yumurta-15-li-p-",
    "Ekmek": "https://www.migros.com.tr/ekmek-p-",
    "Ayçiçek Yağı (1L)": "https://www.migros.com.tr/aycicek-yagi-1-l-p-",
    "Pirinç (1kg)": "https://www.migros.com.tr/pirinc-1-kg-p-"
}

# Örnek ürünler (test için sabit veriler)
SAMPLE_PRODUCTS = {
    "Süt (1L)": {"price": 42.90, "variance": 2.0},
    "Yumurta (15'li)": {"price": 89.90, "variance": 5.0},
    "Ekmek": {"price": 15.00, "variance": 1.0},
    "Ayçiçek Yağı (1L)": {"price": 129.90, "variance": 10.0},
    "Pirinç (1kg)": {"price": 69.90, "variance": 5.0},
    "Makarna (500g)": {"price": 29.90, "variance": 3.0},
    "Şeker (1kg)": {"price": 44.90, "variance": 2.0},
    "Un (2kg)": {"price": 54.90, "variance": 4.0},
    "Tereyağı (250g)": {"price": 119.90, "variance": 8.0},
    "Peynir (500g)": {"price": 189.90, "variance": 15.0}
}


def get_chrome_driver():
    """Selenium için Chrome driver oluşturur."""
    ua = UserAgent()
    user_agent = ua.random
    
    options = Options()
    options.add_argument(f'user-agent={user_agent}')
    options.add_argument('--headless')  # Tarayıcı görünmeden çalışsın
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Bot tespitini zorlaştır
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def scrape_migros_price(driver, url: str) -> float:
    """Migros'tan ürün fiyatını çeker."""
    try:
        driver.get(url)
        time.sleep(random.uniform(2, 4))  # Rastgele bekleme (bot tespitini zorlaştırır)
        
        # Fiyat elementini bul (Migros HTML yapısına göre güncellenmeli)
        # Not: Bu selectorler değişebilir, site yapısına göre güncelleyin
        price_selectors = [
            '.price-new',
            '.product-price',
            '[data-price]',
            '.amount',
            'span.price'
        ]
        
        for selector in price_selectors:
            try:
                price_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                price_text = price_element.text.strip()
                # Fiyatı sayıya çevir (₺, TL, virgül vs. temizle)
                price = float(price_text.replace('₺', '').replace('TL', '')
                            .replace('.', '').replace(',', '.').strip())
                return price
            except:
                continue
        
        return None
    except Exception as e:
        print(f"Hata: {e}")
        return None


def scrape_all_migros_products():
    """Tüm Migros ürünlerini scrape eder."""
    driver = get_chrome_driver()
    today = datetime.now().strftime('%Y-%m-%d')
    
    scraped_count = 0
    
    try:
        for product_name, url in MIGROS_PRODUCTS.items():
            print(f"🔍 {product_name} fiyatı çekiliyor...")
            price = scrape_migros_price(driver, url)
            
            if price:
                insert_product("Migros", product_name, price, "TRY", today)
                print(f"  ✅ {product_name}: {price:.2f} TL")
                scraped_count += 1
            else:
                print(f"  ❌ {product_name} fiyatı alınamadı")
            
            # Her ürün arasında rastgele bekleme
            time.sleep(random.uniform(3, 6))
    
    finally:
        driver.quit()
    
    print(f"\n📊 Toplam {scraped_count}/{len(MIGROS_PRODUCTS)} ürün kaydedildi.")
    return scraped_count


def generate_sample_data(market_name: str = "Migros", days: int = 30):
    """
    Test için örnek veri üretir.
    Gerçek scraping çalışmadığında bu fonksiyonu kullanın.
    """
    from datetime import timedelta
    
    print(f"📦 {days} günlük örnek veri üretiliyor...")
    
    base_date = datetime.now()
    
    for day_offset in range(days):
        current_date = (base_date - timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        for product_name, info in SAMPLE_PRODUCTS.items():
            # Fiyata rastgele varyans ekle (enflasyon simülasyonu)
            inflation_factor = 1 + (day_offset * 0.001)  # Günlük %0.1 enflasyon
            random_variance = random.uniform(-info["variance"], info["variance"])
            price = (info["price"] * inflation_factor) + random_variance
            
            insert_product(market_name, product_name, round(price, 2), "TRY", current_date)
    
    print(f"✅ {days} gün x {len(SAMPLE_PRODUCTS)} ürün = {days * len(SAMPLE_PRODUCTS)} kayıt oluşturuldu!")


def scrape_with_fallback():
    """
    Önce gerçek scraping dener, başarısız olursa örnek veri üretir.
    """
    print("=" * 50)
    print("🛒 Market Fiyat Kazıyıcı Başlatılıyor...")
    print("=" * 50)
    
    try:
        scraped = scrape_all_migros_products()
        if scraped == 0:
            print("\n⚠️ Scraping başarısız, örnek veri üretiliyor...")
            generate_sample_data()
    except Exception as e:
        print(f"\n⚠️ Scraping hatası: {e}")
        print("📦 Örnek veri üretiliyor...")
        generate_sample_data()


if __name__ == '__main__':
    # Test: Örnek veri üret
    generate_sample_data(days=30)
