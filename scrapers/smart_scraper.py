"""
Smart Scraper - Reverse Engineering Tabanlı Fiyat Çekici
=========================================================

Bu scraper "insan gibi görünüp, makine verisini çalma" mantığıyla çalışır.

Çalışma Prensibi:
1. Kapıyı Çalmak (Requests + Fake Headers)
   - User-Agent ile "Ben Chrome'um" yalanı
   - Cookies, Referer gibi headers ile güvenilir görünme

2. Çorbayı Karıştırmak (BeautifulSoup)
   - Ham HTML'i parse edilebilir ağaç yapısına çevirme

3. Gizli Hazineyi Bulmak (JSON Extraction)
   - KASA A: Schema.org / Google için gizli JSON-LD verileri
   - KASA B: Next.js __NEXT_DATA__ uygulama verileri
   - KASA C: JavaScript değişkenleri içindeki veri

4. Cımbızla Çekmek (Data Parsing)
   - JSON'dan price, name, currency, stock bilgilerini çekme

Bu yöntem CSS selector'lara bağımlı değildir - site tasarımı değişse bile 
Google/SEO için konan veri yapıları nadiren değişir.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import random
import time
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime
from fake_useragent import UserAgent


# ============================================================================
# VERİ SINIFLARI
# ============================================================================

@dataclass
class ProductData:
    """Çekilen ürün verisi"""
    name: str
    price: float
    currency: str = "TRY"
    original_price: float = None  # İndirimli ürünlerde orijinal fiyat
    discount_percent: float = None
    in_stock: bool = True
    category: str = "Diğer"
    brand: str = None
    image_url: str = None
    source: str = "unknown"  # Verinin nereden çekildiği
    raw_data: dict = None  # Ham JSON verisi (debug için)


# ============================================================================
# SAHTE KİMLİK OLUŞTURUCU
# ============================================================================

class IdentityGenerator:
    """
    Adım 1: Kapıyı Çalmak
    Sunucuya "Ben bir tarayıcıyım" yalanını söyleyen headers üretir.
    """
    
    def __init__(self):
        try:
            self.ua = UserAgent()
        except:
            self.ua = None
        
        # Yaygın Chrome user-agent'ları (yedek)
        self.chrome_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
    
    def get_headers(self, referer: str = None) -> dict:
        """Gerçekçi HTTP headers üretir."""
        
        # User-Agent seç
        if self.ua:
            try:
                user_agent = self.ua.chrome
            except:
                user_agent = random.choice(self.chrome_agents)
        else:
            user_agent = random.choice(self.chrome_agents)
        
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",  # Do Not Track
        }
        
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"
        
        return headers


# ============================================================================
# JSON HAZINE AVCISI
# ============================================================================

class TreasureHunter:
    """
    Adım 3: Gizli Hazineyi Bulmak
    HTML içindeki gizli JSON verilerini bulur ve çıkarır.
    """
    
    @staticmethod
    def find_schema_org(soup: BeautifulSoup) -> Optional[dict]:
        """
        KASA A: Schema.org / JSON-LD Verileri
        
        Google'ın anlaması için sayfaya gömülmüş yapılandırılmış veri.
        <script type="application/ld+json">...</script>
        
        Bu veri en güvenilir kaynaktır çünkü SEO için kritiktir.
        """
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Tek ürün
                if isinstance(data, dict):
                    if data.get('@type') == 'Product':
                        return data
                    # @graph içinde Product ara
                    if '@graph' in data:
                        for item in data['@graph']:
                            if item.get('@type') == 'Product':
                                return item
                
                # Liste içinde ürün
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            return item
            except json.JSONDecodeError:
                continue
        
        return None
    
    @staticmethod
    def find_next_data(soup: BeautifulSoup) -> Optional[dict]:
        """
        KASA B: Next.js __NEXT_DATA__
        
        Modern React/Next.js siteleri sayfa verilerini bu pakette taşır.
        <script id="__NEXT_DATA__" type="application/json">...</script>
        """
        script = soup.find('script', id='__NEXT_DATA__')
        
        if script and script.string:
            try:
                data = json.loads(script.string)
                return data.get('props', {}).get('pageProps', data)
            except json.JSONDecodeError:
                pass
        
        return None
    
    @staticmethod
    def find_nuxt_data(soup: BeautifulSoup) -> Optional[dict]:
        """
        KASA B2: Nuxt.js __NUXT__
        
        Vue/Nuxt.js siteleri için benzer yapı.
        """
        script = soup.find('script', string=re.compile(r'window\.__NUXT__'))
        
        if script:
            try:
                match = re.search(r'window\.__NUXT__\s*=\s*({.+});?', script.string, re.DOTALL)
                if match:
                    # JSON parse edilemeyebilir (fonksiyonlar içerebilir)
                    # Bu durumda regex ile veri çekmeyi dene
                    pass
            except:
                pass
        
        return None
    
    @staticmethod
    def find_embedded_json(soup: BeautifulSoup, patterns: List[str] = None) -> Optional[dict]:
        """
        KASA C: JavaScript Değişkenleri
        
        Bazı siteler veriyi window.productData, window.__INITIAL_STATE__ gibi
        değişkenlerde tutar.
        """
        if patterns is None:
            patterns = [
                r'window\.productData\s*=\s*({.+?});',
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'var\s+product\s*=\s*({.+?});',
                r'window\.dataLayer\.push\(({.*?"ecommerce".*?})\)',
            ]
        
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
            
            for pattern in patterns:
                try:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except:
                    continue
        
        return None


# ============================================================================
# FİYAT ÇIKARICI
# ============================================================================

class PriceExtractor:
    """
    Adım 4: Cımbızla Çekmek
    Bulunan JSON verilerinden fiyat ve ürün bilgilerini çıkarır.
    """
    
    @staticmethod
    def from_schema_org(data: dict) -> Optional[ProductData]:
        """Schema.org Product verisinden fiyat çıkarır."""
        try:
            name = data.get('name', '')
            
            # Fiyat bilgisi - offers içinde
            offers = data.get('offers', {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            
            price = None
            currency = "TRY"
            
            # Farklı fiyat alanlarını dene
            for price_field in ['price', 'lowPrice', 'highPrice']:
                if price_field in offers:
                    price = float(offers[price_field])
                    break
            
            if not price and 'priceSpecification' in offers:
                spec = offers['priceSpecification']
                if isinstance(spec, list):
                    spec = spec[0]
                price = float(spec.get('price', 0))
            
            currency = offers.get('priceCurrency', 'TRY')
            in_stock = offers.get('availability', '').lower() != 'outofstock'
            
            # Marka
            brand = data.get('brand', {})
            if isinstance(brand, dict):
                brand = brand.get('name', '')
            
            # Resim
            image = data.get('image', '')
            if isinstance(image, list):
                image = image[0] if image else ''
            
            if price and price > 0:
                return ProductData(
                    name=name,
                    price=price,
                    currency=currency,
                    in_stock=in_stock,
                    brand=brand,
                    image_url=image,
                    source="schema.org",
                    raw_data=data
                )
        except Exception as e:
            print(f"Schema.org parse hatası: {e}")
        
        return None
    
    @staticmethod
    def from_next_data(data: dict, site: str = "migros") -> Optional[ProductData]:
        """Next.js verisinden fiyat çıkarır (siteye özel)."""
        try:
            # Migros özel yapısı
            if site == "migros":
                product = data.get('product', data.get('data', {}).get('product', {}))
                
                if not product:
                    # Alternatif yapılar
                    for key in ['productDetail', 'item', 'productData']:
                        if key in data:
                            product = data[key]
                            break
                
                if product:
                    name = product.get('name', product.get('title', ''))
                    price = product.get('price', product.get('salePrice', 0))
                    original_price = product.get('regularPrice', product.get('listPrice'))
                    
                    if isinstance(price, str):
                        price = float(price.replace(',', '.'))
                    
                    return ProductData(
                        name=name,
                        price=price,
                        original_price=original_price,
                        in_stock=product.get('inStock', True),
                        category=product.get('category', 'Diğer'),
                        source="next.js",
                        raw_data=product
                    )
            
            # Genel Next.js yapısı
            # Fiyat içeren herhangi bir alan ara
            def find_price_recursive(obj, depth=0):
                if depth > 5:
                    return None
                
                if isinstance(obj, dict):
                    # Doğrudan fiyat alanları
                    for key in ['price', 'salePrice', 'currentPrice', 'finalPrice']:
                        if key in obj:
                            val = obj[key]
                            if isinstance(val, (int, float)) and val > 0:
                                return obj
                            if isinstance(val, str):
                                try:
                                    if float(val.replace(',', '.')) > 0:
                                        return obj
                                except:
                                    pass
                    
                    # Alt nesnelerde ara
                    for value in obj.values():
                        result = find_price_recursive(value, depth + 1)
                        if result:
                            return result
                
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_price_recursive(item, depth + 1)
                        if result:
                            return result
                
                return None
            
            product = find_price_recursive(data)
            if product:
                name = product.get('name', product.get('title', 'Bilinmeyen Ürün'))
                price = product.get('price', product.get('salePrice', 0))
                
                if isinstance(price, str):
                    price = float(price.replace(',', '.'))
                
                return ProductData(
                    name=name,
                    price=price,
                    source="next.js (recursive)",
                    raw_data=product
                )
                
        except Exception as e:
            print(f"Next.js parse hatası: {e}")
        
        return None


# ============================================================================
# FALLBACK: HTML PARSER
# ============================================================================

class HtmlFallback:
    """
    Gizli kasalar boşsa, klasik HTML parsing yap.
    Bu son çare - daha az güvenilir.
    """
    
    # Site bazlı CSS selector'lar
    SELECTORS = {
        'migros': [
            {'price': '[data-monitor-name="productPrice"]', 'name': '.product-name'},
            {'price': '.price-new', 'name': 'h1.title'},
            {'price': '.product-price', 'name': '.product-title'},
            {'price': 'span[class*="Price"]', 'name': 'h1'},
        ],
        'a101': [
            {'price': '.product-price', 'name': '.product-name'},
            {'price': '.current-price', 'name': 'h1'},
        ],
        'bim': [
            {'price': '.price', 'name': '.product-name'},
        ],
        'carrefour': [
            {'price': '.product-price', 'name': '.product-name'},
            {'price': '[class*="price"]', 'name': 'h1'},
        ],
        'default': [
            {'price': '[class*="price"]', 'name': 'h1'},
            {'price': '[class*="Price"]', 'name': '[class*="title"]'},
            {'price': '.price', 'name': '.title'},
        ]
    }
    
    @staticmethod
    def extract(soup: BeautifulSoup, site: str = "default") -> Optional[ProductData]:
        """HTML'den fiyat çıkarmaya çalışır."""
        selectors = HtmlFallback.SELECTORS.get(site, HtmlFallback.SELECTORS['default'])
        
        for selector_set in selectors:
            try:
                price_elem = soup.select_one(selector_set['price'])
                name_elem = soup.select_one(selector_set['name'])
                
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = HtmlFallback.parse_price(price_text)
                    
                    if price and price > 0:
                        name = name_elem.get_text(strip=True) if name_elem else "Bilinmeyen Ürün"
                        return ProductData(
                            name=name,
                            price=price,
                            source="html_fallback"
                        )
            except:
                continue
        
        return None
    
    @staticmethod
    def parse_price(text: str) -> Optional[float]:
        """Fiyat metnini float'a çevirir."""
        try:
            # Temizle
            cleaned = text.replace('₺', '').replace('TL', '').replace(' ', '').strip()
            
            # Türkçe format: 1.234,56
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace('.', '').replace(',', '.')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            
            # Sayıyı çıkar
            match = re.search(r'(\d+\.?\d*)', cleaned)
            if match:
                return float(match.group(1))
        except:
            pass
        
        return None


# ============================================================================
# ANA SCRAPER SINIFI
# ============================================================================

class SmartScraper:
    """
    Akıllı Fiyat Scraper
    
    Öncelik sırası:
    1. Schema.org JSON-LD (en güvenilir)
    2. Next.js __NEXT_DATA__
    3. Gömülü JavaScript JSON
    4. HTML CSS Selector (son çare)
    """
    
    def __init__(self):
        self.identity = IdentityGenerator()
        self.hunter = TreasureHunter()
        self.session = requests.Session()
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'sources': {}
        }
    
    def detect_site(self, url: str) -> str:
        """URL'den site adını tespit eder."""
        if 'migros' in url.lower():
            return 'migros'
        elif 'a101' in url.lower():
            return 'a101'
        elif 'bim' in url.lower():
            return 'bim'
        elif 'carrefour' in url.lower():
            return 'carrefour'
        elif 'trendyol' in url.lower():
            return 'trendyol'
        elif 'hepsiburada' in url.lower():
            return 'hepsiburada'
        return 'default'
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Sayfayı indirir ve parse eder.
        Adım 1 & 2: Kapıyı çal + Çorbayı karıştır
        """
        try:
            # Rastgele gecikme (bot tespitini zorlaştır)
            time.sleep(random.uniform(1, 3))
            
            # Site ana sayfasını referer olarak kullan
            referer = '/'.join(url.split('/')[:3])
            headers = self.identity.get_headers(referer=referer)
            
            response = self.session.get(
                url, 
                headers=headers, 
                timeout=15,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Encoding düzelt
            response.encoding = response.apparent_encoding or 'utf-8'
            
            # BeautifulSoup ile parse et
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
            
        except requests.RequestException as e:
            print(f"❌ Sayfa indirme hatası: {e}")
            return None
    
    def scrape(self, url: str, expected_name: str = None) -> Optional[ProductData]:
        """
        Tek bir ürünün fiyatını çeker.
        
        Args:
            url: Ürün sayfası URL'i
            expected_name: Beklenen ürün adı (doğrulama için)
        
        Returns:
            ProductData veya None
        """
        self.stats['total'] += 1
        site = self.detect_site(url)
        
        # Sayfayı indir
        soup = self.fetch_page(url)
        if not soup:
            self.stats['failed'] += 1
            return None
        
        product = None
        
        # === KASA A: Schema.org ===
        schema_data = self.hunter.find_schema_org(soup)
        if schema_data:
            product = PriceExtractor.from_schema_org(schema_data)
            if product:
                print(f"✅ Schema.org'dan bulundu: {product.name} - {product.price} {product.currency}")
        
        # === KASA B: Next.js ===
        if not product:
            next_data = self.hunter.find_next_data(soup)
            if next_data:
                product = PriceExtractor.from_next_data(next_data, site)
                if product:
                    print(f"✅ Next.js'den bulundu: {product.name} - {product.price}")
        
        # === KASA C: Gömülü JSON ===
        if not product:
            embedded = self.hunter.find_embedded_json(soup)
            if embedded:
                product = PriceExtractor.from_next_data(embedded, site)
                if product:
                    print(f"✅ Gömülü JSON'dan bulundu: {product.name} - {product.price}")
        
        # === SON ÇARE: HTML Parsing ===
        if not product:
            product = HtmlFallback.extract(soup, site)
            if product:
                print(f"⚠️ HTML fallback kullanıldı: {product.name} - {product.price}")
        
        # Sonuç
        if product:
            self.stats['success'] += 1
            source = product.source
            self.stats['sources'][source] = self.stats['sources'].get(source, 0) + 1
            
            # Beklenen isimle güncelle (CSV'den gelen)
            if expected_name and not product.name:
                product.name = expected_name
            
            return product
        else:
            self.stats['failed'] += 1
            print(f"❌ Fiyat bulunamadı: {url}")
            return None
    
    def scrape_batch(self, items: List[Dict]) -> List[ProductData]:
        """
        Birden fazla ürünü sırayla çeker.
        
        Args:
            items: [{'url': '...', 'name': '...', 'category': '...'}]
        
        Returns:
            ProductData listesi
        """
        results = []
        
        for i, item in enumerate(items, 1):
            print(f"\n[{i}/{len(items)}] {item.get('name', 'Bilinmeyen')}")
            
            product = self.scrape(
                url=item['url'],
                expected_name=item.get('name')
            )
            
            if product:
                # Kategoriyi CSV'den al
                product.category = item.get('category', 'Diğer')
                results.append(product)
            
            # Rate limiting
            if i < len(items):
                delay = random.uniform(2, 5)
                print(f"   ⏳ {delay:.1f}s bekleniyor...")
                time.sleep(delay)
        
        return results
    
    def print_stats(self):
        """İstatistikleri yazdırır."""
        print("\n" + "=" * 50)
        print("📊 SCRAPING İSTATİSTİKLERİ")
        print("=" * 50)
        print(f"Toplam: {self.stats['total']}")
        print(f"Başarılı: {self.stats['success']} ({self.stats['success']/max(1,self.stats['total'])*100:.1f}%)")
        print(f"Başarısız: {self.stats['failed']}")
        print("\nKaynak Dağılımı:")
        for source, count in self.stats['sources'].items():
            print(f"  - {source}: {count}")


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    scraper = SmartScraper()
    
    # Test URL'leri
    test_urls = [
        {
            'url': 'https://www.migros.com.tr/sut-gunluk-1-l-p-1001710',
            'name': 'Süt (1L)',
            'category': 'Temel Gıda'
        }
    ]
    
    print("🔍 Smart Scraper Test")
    print("=" * 50)
    
    results = scraper.scrape_batch(test_urls)
    
    for product in results:
        print(f"\n📦 {product.name}")
        print(f"   💰 Fiyat: {product.price} {product.currency}")
        print(f"   📁 Kategori: {product.category}")
        print(f"   📡 Kaynak: {product.source}")
    
    scraper.print_stats()
