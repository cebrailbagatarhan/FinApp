"""
Enflasyon Hesaplama Motoru (calculator.py)
==========================================
TÜİK ve İTO metodolojisini simüle eden ağırlıklı enflasyon hesaplayıcı.

Metodoloji:
- TÜİK: Tüketici Fiyat Endeksi (TÜFE) ağırlıkları
- İTO: İstanbul Ticaret Odası ücretliler geçinme endeksi ağırlıkları
- Ham: Eşit ağırlıklı basit ortalama

Formül:
    Enflasyon = Σ(Kategori_Değişimi × Kategori_Ağırlığı) / 100
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection


# ============================================================================
# BÖLÜM 1: SABİT TANIMLAR (CONFIG)
# ============================================================================

class WeightSource(Enum):
    """Ağırlık kaynağı türleri"""
    TUIK = "tuik"
    ITO = "ito"
    EQUAL = "equal"  # Eşit ağırlık (ham)


# TÜİK TÜFE Ağırlıkları (2024 Yılı Baz Alınmıştır)
# Kaynak: TÜİK Tüketici Fiyat Endeksi Ana Grupları
TUIK_WEIGHTS = {
    "Gıda ve Alkolsüz İçecekler": 25.48,
    "Alkollü İçecekler ve Tütün": 4.25,
    "Giyim ve Ayakkabı": 6.42,
    "Konut": 14.20,  # Kira, Elektrik, Su, Doğalgaz
    "Ev Eşyası": 6.58,
    "Sağlık": 2.87,
    "Ulaştırma": 15.08,  # Benzin, Otomobil, Toplu Taşıma
    "Haberleşme": 3.62,
    "Eğlence ve Kültür": 2.98,
    "Eğitim": 3.04,
    "Lokanta ve Otel": 8.78,
    "Çeşitli Mal ve Hizmetler": 6.70
}

# İTO Ücretliler Geçinme Endeksi Ağırlıkları (Yaklaşık)
# Kaynak: İstanbul Ticaret Odası
ITO_WEIGHTS = {
    "Gıda ve Alkolsüz İçecekler": 28.50,
    "Alkollü İçecekler ve Tütün": 3.80,
    "Giyim ve Ayakkabı": 7.10,
    "Konut": 16.40,
    "Ev Eşyası": 5.90,
    "Sağlık": 2.50,
    "Ulaştırma": 12.80,
    "Haberleşme": 4.20,
    "Eğlence ve Kültür": 3.10,
    "Eğitim": 4.50,
    "Lokanta ve Otel": 6.20,
    "Çeşitli Mal ve Hizmetler": 5.00
}


# ============================================================================
# BÖLÜM 2: ÜRÜN -> KATEGORİ EŞLEŞTİRMESİ (MAPPING)
# ============================================================================

# Alt kategorileri TÜİK ana gruplarına eşleştirme
CATEGORY_MAPPING = {
    # Gıda ve Alkolsüz İçecekler
    "Temel Gıda": "Gıda ve Alkolsüz İçecekler",
    "Süt Ürünleri": "Gıda ve Alkolsüz İçecekler",
    "Yağ": "Gıda ve Alkolsüz İçecekler",
    "Fırın": "Gıda ve Alkolsüz İçecekler",
    "Konserve": "Gıda ve Alkolsüz İçecekler",
    "Bakliyat": "Gıda ve Alkolsüz İçecekler",
    "Et/Tavuk": "Gıda ve Alkolsüz İçecekler",
    "Et": "Gıda ve Alkolsüz İçecekler",
    "Tavuk": "Gıda ve Alkolsüz İçecekler",
    "Balık": "Gıda ve Alkolsüz İçecekler",
    "Meyve/Sebze": "Gıda ve Alkolsüz İçecekler",
    "Meyve": "Gıda ve Alkolsüz İçecekler",
    "Sebze": "Gıda ve Alkolsüz İçecekler",
    "İçecek": "Gıda ve Alkolsüz İçecekler",
    "Alkolsüz İçecek": "Gıda ve Alkolsüz İçecekler",
    "Çay": "Gıda ve Alkolsüz İçecekler",
    "Kahve": "Gıda ve Alkolsüz İçecekler",
    "Gıda": "Gıda ve Alkolsüz İçecekler",
    
    # Alkollü İçecekler ve Tütün
    "Alkollü İçecek": "Alkollü İçecekler ve Tütün",
    "Sigara": "Alkollü İçecekler ve Tütün",
    "Tütün": "Alkollü İçecekler ve Tütün",
    
    # Giyim ve Ayakkabı
    "Giyim": "Giyim ve Ayakkabı",
    "Ayakkabı": "Giyim ve Ayakkabı",
    "Tekstil": "Giyim ve Ayakkabı",
    
    # Konut
    "Konut": "Konut",
    "Kira": "Konut",
    "Elektrik": "Konut",
    "Su": "Konut",
    "Doğalgaz": "Konut",
    "Yakıt": "Konut",
    
    # Ev Eşyası
    "Ev Eşyası": "Ev Eşyası",
    "Mobilya": "Ev Eşyası",
    "Beyaz Eşya": "Ev Eşyası",
    "Mutfak": "Ev Eşyası",
    
    # Sağlık
    "Sağlık": "Sağlık",
    "İlaç": "Sağlık",
    "Tıbbi Ürün": "Sağlık",
    
    # Ulaştırma
    "Ulaştırma": "Ulaştırma",
    "Benzin": "Ulaştırma",
    "Motorin": "Ulaştırma",
    "Akaryakıt": "Ulaştırma",
    "Otomobil": "Ulaştırma",
    "Toplu Taşıma": "Ulaştırma",
    
    # Haberleşme
    "Haberleşme": "Haberleşme",
    "Telefon": "Haberleşme",
    "İnternet": "Haberleşme",
    
    # Eğlence ve Kültür
    "Eğlence": "Eğlence ve Kültür",
    "Kültür": "Eğlence ve Kültür",
    "Kitap": "Eğlence ve Kültür",
    "Elektronik": "Eğlence ve Kültür",
    
    # Eğitim
    "Eğitim": "Eğitim",
    "Okul": "Eğitim",
    "Kurs": "Eğitim",
    
    # Lokanta ve Otel
    "Lokanta": "Lokanta ve Otel",
    "Otel": "Lokanta ve Otel",
    "Yemek": "Lokanta ve Otel",
    "Restoran": "Lokanta ve Otel",
    
    # Çeşitli Mal ve Hizmetler
    "Temizlik": "Çeşitli Mal ve Hizmetler",
    "Kişisel Bakım": "Çeşitli Mal ve Hizmetler",
    "Kozmetik": "Çeşitli Mal ve Hizmetler",
    "Hizmet": "Çeşitli Mal ve Hizmetler",
    "Diğer": "Çeşitli Mal ve Hizmetler"
}

# Varsayılan kategori (eşleşme bulunamazsa)
DEFAULT_CATEGORY = "Çeşitli Mal ve Hizmetler"


# ============================================================================
# BÖLÜM 3: VERİ SINIFLARI
# ============================================================================

@dataclass
class CategoryData:
    """Kategori bazlı enflasyon verisi"""
    category: str
    main_category: str
    product_count: int
    avg_change_pct: float
    min_change_pct: float
    max_change_pct: float
    products: List[Dict] = field(default_factory=list)


@dataclass
class InflationResult:
    """Enflasyon hesaplama sonucu"""
    success: bool
    tuik_inflation: float = 0.0
    ito_inflation: float = 0.0
    raw_inflation: float = 0.0
    
    # Detaylar
    period_days: int = 0
    start_date: str = ""
    end_date: str = ""
    total_products: int = 0
    
    # Kategori bazlı veriler
    category_breakdown: Dict[str, CategoryData] = field(default_factory=dict)
    tuik_weights_used: Dict[str, float] = field(default_factory=dict)
    ito_weights_used: Dict[str, float] = field(default_factory=dict)
    
    # Hata durumunda
    error: str = ""
    
    def to_dict(self) -> Dict:
        """Sonucu dictionary'e çevir"""
        return {
            'success': self.success,
            'tuik_inflation': round(self.tuik_inflation, 2),
            'ito_inflation': round(self.ito_inflation, 2),
            'raw_inflation': round(self.raw_inflation, 2),
            'period_days': self.period_days,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'total_products': self.total_products,
            'category_breakdown': {
                k: {
                    'category': v.category,
                    'main_category': v.main_category,
                    'product_count': v.product_count,
                    'avg_change_pct': round(v.avg_change_pct, 2),
                    'min_change_pct': round(v.min_change_pct, 2),
                    'max_change_pct': round(v.max_change_pct, 2)
                } for k, v in self.category_breakdown.items()
            },
            'tuik_weights_used': self.tuik_weights_used,
            'ito_weights_used': self.ito_weights_used,
            'error': self.error
        }


# ============================================================================
# BÖLÜM 4: YARDIMCI FONKSİYONLAR
# ============================================================================

def get_main_category(sub_category: str) -> str:
    """
    Alt kategoriyi TÜİK ana kategorisine eşleştirir.
    
    Args:
        sub_category: Ürünün alt kategorisi (örn: "Süt Ürünleri")
    
    Returns:
        Ana kategori adı (örn: "Gıda ve Alkolsüz İçecekler")
    """
    if not sub_category:
        return DEFAULT_CATEGORY
    
    # Direkt eşleşme
    if sub_category in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[sub_category]
    
    # Case-insensitive arama
    for key, value in CATEGORY_MAPPING.items():
        if key.lower() == sub_category.lower():
            return value
    
    # Kısmi eşleşme
    for key, value in CATEGORY_MAPPING.items():
        if key.lower() in sub_category.lower() or sub_category.lower() in key.lower():
            return value
    
    return DEFAULT_CATEGORY


def normalize_weights(weights: Dict[str, float], active_categories: List[str]) -> Dict[str, float]:
    """
    Ağırlıkları normalize eder - sadece aktif kategorilerin ağırlıkları toplamı 100 olacak şekilde.
    
    Args:
        weights: Orijinal ağırlıklar
        active_categories: Veri bulunan kategoriler
    
    Returns:
        Normalize edilmiş ağırlıklar
    """
    if not active_categories:
        return {}
    
    active_weights = {cat: weights.get(cat, 0) for cat in active_categories}
    total = sum(active_weights.values())
    
    if total == 0:
        # Eşit dağıt
        equal_weight = 100 / len(active_categories)
        return {cat: equal_weight for cat in active_categories}
    
    # Normalize et
    return {cat: (w / total) * 100 for cat, w in active_weights.items()}


def load_product_categories() -> Dict[str, str]:
    """
    CSV dosyasından ürün-kategori eşleştirmesini yükler.
    
    Returns:
        Dict[ürün_adı, kategori]
    """
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'urunler.csv')
    
    try:
        df = pd.read_csv(csv_path)
        if 'Kategori' in df.columns and 'Ürün Adı' in df.columns:
            return dict(zip(df['Ürün Adı'].str.lower(), df['Kategori']))
    except Exception as e:
        print(f"CSV yükleme hatası: {e}")
    
    return {}


# ============================================================================
# BÖLÜM 5: ANA HESAPLAMA MOTORU
# ============================================================================

class InflationCalculator:
    """
    TÜİK ve İTO metodolojisini simüle eden enflasyon hesaplayıcı.
    
    Usage:
        calculator = InflationCalculator()
        result = calculator.calculate(days=30)
        print(f"TÜİK: {result.tuik_inflation}%")
        print(f"İTO: {result.ito_inflation}%")
        print(f"Ham: {result.raw_inflation}%")
    """
    
    def __init__(self, custom_tuik_weights: Dict = None, custom_ito_weights: Dict = None):
        """
        Hesaplayıcıyı başlatır.
        
        Args:
            custom_tuik_weights: Özel TÜİK ağırlıkları (opsiyonel)
            custom_ito_weights: Özel İTO ağırlıkları (opsiyonel)
        """
        self.tuik_weights = custom_tuik_weights or TUIK_WEIGHTS.copy()
        self.ito_weights = custom_ito_weights or ITO_WEIGHTS.copy()
        self.product_categories = load_product_categories()
    
    def _get_product_data(self, days: int, market_name: str = None) -> Tuple[pd.DataFrame, str, str]:
        """
        Veritabanından ürün fiyat verilerini çeker.
        
        Returns:
            Tuple of (DataFrame, start_date, end_date)
        """
        conn = get_connection()
        market_filter = "AND market_name = ?" if market_name else ""
        base_params = [market_name] if market_name else []
        
        # Tarih aralığını bul
        date_query = f"""
            SELECT MIN(date) as start_date, MAX(date) as end_date
            FROM products
            WHERE date >= date('now', ? || ' days')
            {market_filter}
        """
        date_params = [str(-int(days))] + base_params
        dates = pd.read_sql_query(date_query, conn, params=date_params)
        
        if dates.empty or dates['start_date'].iloc[0] is None:
            conn.close()
            return pd.DataFrame(), "", ""
        
        start_date = dates['start_date'].iloc[0]
        end_date = dates['end_date'].iloc[0]
        
        # Önce tablo yapısını kontrol et - category sütunu var mı?
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cursor.fetchall()]
        has_category = 'category' in columns
        
        # Ürün fiyatlarını çek
        if has_category:
            query = f"""
                WITH first_prices AS (
                    SELECT product_name, category, AVG(price) as first_price
                    FROM products
                    WHERE date = ? {market_filter}
                    GROUP BY product_name, category
                ),
                last_prices AS (
                    SELECT product_name, category, AVG(price) as last_price
                    FROM products
                    WHERE date = ? {market_filter}
                    GROUP BY product_name, category
                )
                SELECT 
                    f.product_name,
                    COALESCE(f.category, 'Diğer') as category,
                    f.first_price,
                    l.last_price,
                    ((l.last_price - f.first_price) / f.first_price) * 100 as change_pct
                FROM first_prices f
                JOIN last_prices l ON f.product_name = l.product_name
                WHERE f.first_price > 0
                ORDER BY change_pct DESC
            """
        else:
            # Category sütunu yoksa, ürün adından kategori çıkar
            query = f"""
                WITH first_prices AS (
                    SELECT product_name, AVG(price) as first_price
                    FROM products
                    WHERE date = ? {market_filter}
                    GROUP BY product_name
                ),
                last_prices AS (
                    SELECT product_name, AVG(price) as last_price
                    FROM products
                    WHERE date = ? {market_filter}
                    GROUP BY product_name
                )
                SELECT 
                    f.product_name,
                    'Diğer' as category,
                    f.first_price,
                    l.last_price,
                    ((l.last_price - f.first_price) / f.first_price) * 100 as change_pct
                FROM first_prices f
                JOIN last_prices l ON f.product_name = l.product_name
                WHERE f.first_price > 0
                ORDER BY change_pct DESC
            """
        
        query_params = [start_date] + base_params + [end_date] + base_params
        df = pd.read_sql_query(query, conn, params=query_params)
        conn.close()
        
        return df, start_date, end_date
    
    def _assign_main_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Her ürüne TÜİK ana kategorisini atar.
        CSV dosyasından kategori bilgisini alır.
        """
        if df.empty:
            return df
        
        # CSV'den kategori eşleştirmesini yükle
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'urunler.csv')
        csv_categories = {}
        
        try:
            csv_df = pd.read_csv(csv_path)
            if 'Kategori' in csv_df.columns and 'Ürün Adı' in csv_df.columns:
                for _, row in csv_df.iterrows():
                    # Ürün adını normalize et
                    product_name = str(row['Ürün Adı']).lower().strip()
                    csv_categories[product_name] = row['Kategori']
        except Exception as e:
            print(f"CSV okuma hatası: {e}")
        
        # Her ürün için kategori ata
        def assign_category(row):
            product_name = str(row['product_name']).lower().strip()
            db_category = row.get('category', 'Diğer')
            
            # Önce CSV'den bak
            for csv_name, csv_cat in csv_categories.items():
                # Tam eşleşme veya kısmi eşleşme
                if csv_name in product_name or product_name in csv_name:
                    return get_main_category(csv_cat)
            
            # CSV'de yoksa DB kategorisini kullan
            return get_main_category(db_category)
        
        df['main_category'] = df.apply(assign_category, axis=1)
        
        return df
    
    def _calculate_category_changes(self, df: pd.DataFrame) -> Dict[str, CategoryData]:
        """
        Her kategori için ortalama fiyat değişimini hesaplar.
        """
        category_data = {}
        
        if df.empty:
            return category_data
        
        for main_cat in df['main_category'].unique():
            cat_df = df[df['main_category'] == main_cat]
            
            category_data[main_cat] = CategoryData(
                category=main_cat,
                main_category=main_cat,
                product_count=len(cat_df),
                avg_change_pct=cat_df['change_pct'].mean(),
                min_change_pct=cat_df['change_pct'].min(),
                max_change_pct=cat_df['change_pct'].max(),
                products=[
                    {
                        'name': row['product_name'],
                        'sub_category': row['category'],
                        'change_pct': row['change_pct'],
                        'first_price': row['first_price'],
                        'last_price': row['last_price']
                    }
                    for _, row in cat_df.iterrows()
                ]
            )
        
        return category_data
    
    def _calculate_weighted_inflation(
        self, 
        category_changes: Dict[str, CategoryData], 
        weights: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Ağırlıklı enflasyon hesaplar.
        
        Formül: Σ(Kategori_Değişimi × Kategori_Ağırlığı) / 100
        
        Returns:
            Tuple of (inflation_rate, weights_used)
        """
        active_categories = list(category_changes.keys())
        normalized_weights = normalize_weights(weights, active_categories)
        
        weighted_sum = 0.0
        for category, data in category_changes.items():
            weight = normalized_weights.get(category, 0)
            weighted_sum += data.avg_change_pct * weight
        
        inflation = weighted_sum / 100
        
        return inflation, normalized_weights
    
    def _calculate_raw_inflation(self, category_changes: Dict[str, CategoryData]) -> float:
        """
        Eşit ağırlıklı (ham) enflasyon hesaplar.
        """
        if not category_changes:
            return 0.0
        
        total_change = sum(data.avg_change_pct for data in category_changes.values())
        return total_change / len(category_changes)
    
    def calculate(self, days: int = 30, market_name: str = None) -> InflationResult:
        """
        Enflasyon hesaplar ve 3 farklı sonuç döndürür.
        
        Args:
            days: Kaç günlük period
            market_name: Opsiyonel market filtresi
        
        Returns:
            InflationResult object with:
            - tuik_inflation: TÜİK ağırlıklı kişisel enflasyon
            - ito_inflation: İTO ağırlıklı kişisel enflasyon
            - raw_inflation: Ham (eşit ağırlıklı) enflasyon
        """
        # Veriyi çek
        df, start_date, end_date = self._get_product_data(days, market_name)
        
        if df.empty:
            return InflationResult(
                success=False,
                error="Yeterli veri bulunamadı. Market botunu çalıştırın veya örnek veri yükleyin."
            )
        
        # Ana kategorileri ata
        df = self._assign_main_categories(df)
        
        # Kategori bazlı değişimleri hesapla
        category_changes = self._calculate_category_changes(df)
        
        # TÜİK ağırlıklı enflasyon
        tuik_inflation, tuik_weights_used = self._calculate_weighted_inflation(
            category_changes, self.tuik_weights
        )
        
        # İTO ağırlıklı enflasyon
        ito_inflation, ito_weights_used = self._calculate_weighted_inflation(
            category_changes, self.ito_weights
        )
        
        # Ham (eşit ağırlıklı) enflasyon
        raw_inflation = self._calculate_raw_inflation(category_changes)
        
        return InflationResult(
            success=True,
            tuik_inflation=tuik_inflation,
            ito_inflation=ito_inflation,
            raw_inflation=raw_inflation,
            period_days=days,
            start_date=start_date,
            end_date=end_date,
            total_products=len(df),
            category_breakdown=category_changes,
            tuik_weights_used=tuik_weights_used,
            ito_weights_used=ito_weights_used
        )
    
    def compare_with_official(self, official_tuik: float, official_ito: float = None) -> Dict:
        """
        Kişisel enflasyonu resmi rakamlarla karşılaştırır.
        
        Args:
            official_tuik: Resmi TÜİK enflasyonu
            official_ito: Resmi İTO enflasyonu (opsiyonel)
        
        Returns:
            Karşılaştırma sonuçları
        """
        result = self.calculate()
        
        if not result.success:
            return {'success': False, 'error': result.error}
        
        comparison = {
            'success': True,
            'personal': {
                'tuik_method': result.tuik_inflation,
                'ito_method': result.ito_inflation,
                'raw': result.raw_inflation
            },
            'official': {
                'tuik': official_tuik,
                'ito': official_ito
            },
            'difference': {
                'tuik_vs_official': result.tuik_inflation - official_tuik,
                'personal_higher': result.tuik_inflation > official_tuik
            }
        }
        
        if official_ito:
            comparison['difference']['ito_vs_official'] = result.ito_inflation - official_ito
        
        # Yorum oluştur
        diff = comparison['difference']['tuik_vs_official']
        if diff > 5:
            comparison['comment'] = "⚠️ Kişisel enflasyonunuz resmi rakamların çok üzerinde!"
        elif diff > 0:
            comparison['comment'] = "📈 Kişisel enflasyonunuz resmi rakamların biraz üzerinde."
        elif diff < -5:
            comparison['comment'] = "✅ Kişisel enflasyonunuz resmi rakamların çok altında!"
        else:
            comparison['comment'] = "📊 Kişisel enflasyonunuz resmi rakamlara yakın."
        
        return comparison


# ============================================================================
# BÖLÜM 6: KISA FONKSİYONLAR (Kolay Erişim)
# ============================================================================

def calculate_inflation(days: int = 30, market_name: str = None) -> Dict:
    """
    Kısa yol fonksiyonu - Hızlı enflasyon hesaplama.
    
    Returns:
        Dict with tuik_inflation, ito_inflation, raw_inflation
    """
    calculator = InflationCalculator()
    result = calculator.calculate(days, market_name)
    return result.to_dict()


def get_category_weights(source: str = "tuik") -> Dict[str, float]:
    """
    Belirtilen kaynağın ağırlıklarını döndürür.
    
    Args:
        source: "tuik" veya "ito"
    
    Returns:
        Ağırlıklar dictionary'si
    """
    if source.lower() == "ito":
        return ITO_WEIGHTS.copy()
    return TUIK_WEIGHTS.copy()


def get_category_for_product(product_category: str) -> str:
    """
    Ürün kategorisini TÜİK ana kategorisine eşleştirir.
    
    Args:
        product_category: Ürünün alt kategorisi
    
    Returns:
        TÜİK ana kategori adı
    """
    return get_main_category(product_category)


# ============================================================================
# BÖLÜM 7: JSON EXPORT/IMPORT
# ============================================================================

def export_weights_to_json(filepath: str = "inflation_weights.json"):
    """
    Ağırlıkları JSON dosyasına yazar.
    """
    data = {
        "tuik_weights": TUIK_WEIGHTS,
        "ito_weights": ITO_WEIGHTS,
        "category_mapping": CATEGORY_MAPPING,
        "default_category": DEFAULT_CATEGORY,
        "last_updated": datetime.now().isoformat()
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Ağırlıklar {filepath} dosyasına kaydedildi.")


def load_weights_from_json(filepath: str = "inflation_weights.json") -> Tuple[Dict, Dict]:
    """
    JSON dosyasından ağırlıkları okur.
    
    Returns:
        Tuple of (tuik_weights, ito_weights)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('tuik_weights', TUIK_WEIGHTS), data.get('ito_weights', ITO_WEIGHTS)
    except FileNotFoundError:
        print(f"⚠️ {filepath} bulunamadı. Varsayılan ağırlıklar kullanılacak.")
        return TUIK_WEIGHTS, ITO_WEIGHTS


# ============================================================================
# BÖLÜM 8: TEST / DEMO
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ENFLASYON HESAPLAMA MOTORU - TEST")
    print("=" * 60)
    
    # Hesaplayıcı oluştur
    calculator = InflationCalculator()
    
    # 30 günlük enflasyon hesapla
    result = calculator.calculate(days=30)
    
    if result.success:
        print(f"\n📅 Dönem: {result.start_date} - {result.end_date} ({result.period_days} gün)")
        print(f"📦 Toplam Ürün: {result.total_products}")
        
        print("\n" + "-" * 40)
        print("ENFLASYON SONUÇLARI:")
        print("-" * 40)
        print(f"🔹 TÜİK Ağırlıklı  : %{result.tuik_inflation:.2f}")
        print(f"🔹 İTO Ağırlıklı   : %{result.ito_inflation:.2f}")
        print(f"🔹 Ham (Eşit Ağrlk): %{result.raw_inflation:.2f}")
        
        print("\n" + "-" * 40)
        print("KATEGORİ BAZLI DEĞİŞİMLER:")
        print("-" * 40)
        
        for cat, data in sorted(result.category_breakdown.items(), 
                                key=lambda x: x[1].avg_change_pct, reverse=True):
            tuik_w = result.tuik_weights_used.get(cat, 0)
            print(f"\n📁 {cat}")
            print(f"   Ürün Sayısı: {data.product_count}")
            print(f"   Ortalama Değişim: %{data.avg_change_pct:.2f}")
            print(f"   Min/Max: %{data.min_change_pct:.2f} / %{data.max_change_pct:.2f}")
            print(f"   TÜİK Ağırlığı: %{tuik_w:.2f}")
    else:
        print(f"\n❌ Hata: {result.error}")
    
    print("\n" + "=" * 60)
