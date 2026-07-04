"""
Enflasyon Hesaplama Modülü
- Market sepet fiyat değişimi hesaplama
- Resmi enflasyonla karşılaştırma
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection


def calculate_basket_inflation(market_name: str = None, days: int = 30) -> dict:
    """
    Market sepetindeki ürünlerin fiyat değişimini hesaplar.
    
    Returns:
        dict: {
            'basket_inflation': float,  # Yüzde değişim
            'products': list,  # Ürün bazlı değişimler
            'start_date': str,
            'end_date': str
        }
    """
    conn = get_connection()
    
    # Market filtresi (parametrik)
    market_filter = "AND market_name = ?" if market_name else ""
    base_params = [market_name] if market_name else []
    
    # Son tarih ve başlangıç tarihi
    date_query = f"""
        SELECT 
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM products
        WHERE date >= date('now', ? || ' days')
        {market_filter}
    """
    date_params = [str(-int(days))] + base_params
    
    dates = pd.read_sql_query(date_query, conn, params=date_params)
    
    if dates.empty or dates['start_date'].iloc[0] is None:
        conn.close()
        return {
            'basket_inflation': 0,
            'products': [],
            'start_date': None,
            'end_date': None
        }
    
    start_date = dates['start_date'].iloc[0]
    end_date = dates['end_date'].iloc[0]
    
    # Her ürün için başlangıç ve bitiş fiyatlarını al
    query = f"""
        WITH first_prices AS (
            SELECT product_name, price as first_price
            FROM products
            WHERE date = ? {market_filter}
        ),
        last_prices AS (
            SELECT product_name, price as last_price
            FROM products
            WHERE date = ? {market_filter}
        )
        SELECT 
            f.product_name,
            f.first_price,
            l.last_price,
            ROUND(((l.last_price - f.first_price) / f.first_price) * 100, 2) as change_pct
        FROM first_prices f
        JOIN last_prices l ON f.product_name = l.product_name
        ORDER BY change_pct DESC
    """
    product_params = [start_date] + base_params + [end_date] + base_params
    
    products_df = pd.read_sql_query(query, conn, params=product_params)
    conn.close()
    
    if products_df.empty:
        return {
            'basket_inflation': 0,
            'products': [],
            'start_date': start_date,
            'end_date': end_date
        }
    
    # Sepet enflasyonu (basit ortalama)
    basket_inflation = products_df['change_pct'].mean()
    
    products_list = products_df.to_dict('records')
    
    return {
        'basket_inflation': round(basket_inflation, 2),
        'products': products_list,
        'start_date': start_date,
        'end_date': end_date,
        'period_days': days
    }


def get_official_inflation(country: str = "TR") -> dict:
    """
    Resmi enflasyon verilerini getirir.
    
    Returns:
        dict: {'current': float, 'previous': float, 'trend': str}
    """
    conn = get_connection()
    
    query = """
        SELECT date, value
        FROM macro_data
        WHERE country = ? AND data_type = 'CPI'
        ORDER BY date DESC
        LIMIT 2
    """
    
    df = pd.read_sql_query(query, conn, params=(country,))
    conn.close()
    
    if df.empty:
        return {'current': 0, 'previous': 0, 'trend': 'unknown'}
    
    current = df['value'].iloc[0] if len(df) > 0 else 0
    previous = df['value'].iloc[1] if len(df) > 1 else current
    
    if current > previous:
        trend = 'rising'
    elif current < previous:
        trend = 'falling'
    else:
        trend = 'stable'
    
    return {
        'current': current,
        'previous': previous,
        'trend': trend,
        'country': country
    }


def compare_inflation(market_name: str = None, country: str = "TR", days: int = 30) -> dict:
    """
    Market enflasyonunu resmi enflasyonla karşılaştırır.
    
    Returns:
        dict: Karşılaştırma sonuçları ve yorum
    """
    basket = calculate_basket_inflation(market_name, days)
    official = get_official_inflation(country)
    
    basket_inf = basket['basket_inflation']
    official_inf = official['current']
    
    # Fark hesapla (aylık bazda normalize et)
    # Resmi enflasyon yıllık, market enflasyonu belirtilen period için
    monthly_official = official_inf / 12  # Yıllık -> Aylık
    daily_official = official_inf / 365  # Yıllık -> Günlük
    period_official = daily_official * days  # Period için beklenen resmi enflasyon
    
    difference = basket_inf - period_official
    
    # Yorum
    if difference > 5:
        interpretation = "⚠️ Market enflasyonu resmi verilerden çok yüksek! Fiyatlar hızla artıyor."
        alert_level = "high"
    elif difference > 2:
        interpretation = "📊 Market enflasyonu resmi verilerden yüksek. Dikkatli olun."
        alert_level = "medium"
    elif difference < -2:
        interpretation = "✅ Market enflasyonu resmi verilerden düşük. İyi haber!"
        alert_level = "low"
    else:
        interpretation = "📈 Market enflasyonu resmi verilerle uyumlu."
        alert_level = "normal"
    
    return {
        'basket_inflation': basket_inf,
        'official_inflation_yearly': official_inf,
        'official_inflation_period': round(period_official, 2),
        'difference': round(difference, 2),
        'interpretation': interpretation,
        'alert_level': alert_level,
        'basket_details': basket,
        'official_details': official
    }


def get_price_trend(product_name: str, market_name: str = None, days: int = 30) -> pd.DataFrame:
    """
    Belirli bir ürünün fiyat trendini getirir.
    """
    conn = get_connection()
    
    market_filter = "AND market_name = ?" if market_name else ""
    
    query = f"""
        SELECT date, price, market_name
        FROM products
        WHERE product_name = ? 
        AND date >= date('now', ? || ' days')
        {market_filter}
        ORDER BY date
    """
    
    params = [product_name, str(-int(days))]
    if market_name:
        params.append(market_name)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df


def get_all_products_summary() -> pd.DataFrame:
    """Tüm ürünlerin özet tablosunu getirir."""
    conn = get_connection()
    
    query = """
        WITH latest AS (
            SELECT product_name, market_name, price, date,
                   ROW_NUMBER() OVER (PARTITION BY product_name, market_name ORDER BY date DESC) as rn
            FROM products
        ),
        oldest AS (
            SELECT product_name, market_name, price as first_price,
                   ROW_NUMBER() OVER (PARTITION BY product_name, market_name ORDER BY date ASC) as rn
            FROM products
            WHERE date >= date('now', '-30 days')
        )
        SELECT 
            l.product_name,
            l.market_name,
            l.price as current_price,
            o.first_price,
            ROUND(((l.price - o.first_price) / o.first_price) * 100, 2) as change_30d
        FROM latest l
        JOIN oldest o ON l.product_name = o.product_name 
            AND l.market_name = o.market_name
        WHERE l.rn = 1 AND o.rn = 1
        ORDER BY change_30d DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


if __name__ == '__main__':
    print("=" * 60)
    print("📊 Enflasyon Analizi")
    print("=" * 60)
    
    # Market enflasyonu hesapla
    basket = calculate_basket_inflation(days=30)
    print(f"\n🛒 Market Sepet Enflasyonu (30 gün): {basket['basket_inflation']}%")
    
    if basket['products']:
        print("\nÜrün Bazlı Değişimler:")
        for p in basket['products'][:5]:
            emoji = "🔴" if p['change_pct'] > 5 else "🟡" if p['change_pct'] > 0 else "🟢"
            print(f"  {emoji} {p['product_name']}: {p['change_pct']}%")
    
    # Karşılaştırma
    print("\n" + "=" * 60)
    comparison = compare_inflation(days=30)
    print(f"\n📈 Karşılaştırma:")
    print(f"  Market Enflasyonu: {comparison['basket_inflation']}%")
    print(f"  Resmi Enflasyon (Yıllık): {comparison['official_inflation_yearly']}%")
    print(f"  Resmi Enflasyon ({30} gün): {comparison['official_inflation_period']}%")
    print(f"  Fark: {comparison['difference']}%")
    print(f"\n{comparison['interpretation']}")
