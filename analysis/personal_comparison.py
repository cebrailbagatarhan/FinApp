"""
Kişisel Enflasyon vs Hisse Getirisi Karşılaştırma Motoru
Senin market sepetindeki enflasyonu hesaplar ve seçtiğin hisseyle karşılaştırır.

v2.0: TÜİK/İTO metodolojisi entegrasyonu ile calculator.py kullanımı
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection
from analysis.stock_search import analyze_stock
from analysis.calculator import InflationCalculator, calculate_inflation


def calculate_personal_inflation(days: int = 30, market_name: str = None) -> Dict:
    """
    Kişisel market sepetindeki enflasyonu hesaplar.
    
    Args:
        days: Kaç günlük period
        market_name: Opsiyonel market filtresi
    
    Returns:
        Dict with inflation details
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
        return {
            'success': False,
            'error': 'Yeterli veri yok. Önce market botunu çalıştırın.',
            'inflation': 0
        }
    
    start_date = dates['start_date'].iloc[0]
    end_date = dates['end_date'].iloc[0]
    
    # Her ürün için başlangıç ve bitiş fiyatlarını hesapla
    product_query = f"""
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
            f.first_price,
            l.last_price,
            ((l.last_price - f.first_price) / f.first_price) * 100 as change_pct
        FROM first_prices f
        JOIN last_prices l ON f.product_name = l.product_name
        ORDER BY change_pct DESC
    """
    product_params = [start_date] + base_params + [end_date] + base_params
    
    products = pd.read_sql_query(product_query, conn, params=product_params)
    conn.close()
    
    if products.empty:
        return {
            'success': False,
            'error': 'Ürün verisi bulunamadı',
            'inflation': 0
        }
    
    # Sepet enflasyonu (basit ortalama) - HAM
    basket_inflation = products['change_pct'].mean()
    
    # Ağırlıklı ortalama (fiyata göre)
    total_value = products['last_price'].sum()
    weighted_inflation = (products['change_pct'] * products['last_price'] / total_value).sum()
    
    # TÜİK/İTO Metodolojisi ile hesapla
    calculator = InflationCalculator()
    advanced_result = calculator.calculate(days=days, market_name=market_name)
    
    tuik_inflation = advanced_result.tuik_inflation if advanced_result.success else basket_inflation
    ito_inflation = advanced_result.ito_inflation if advanced_result.success else basket_inflation
    
    # En çok artan ve azalan ürünler
    top_increases = products.nlargest(5, 'change_pct')[['product_name', 'change_pct']].to_dict('records')
    top_decreases = products.nsmallest(5, 'change_pct')[['product_name', 'change_pct']].to_dict('records')
    
    return {
        'success': True,
        'inflation': round(basket_inflation, 2),  # Ham enflasyon
        'weighted_inflation': round(weighted_inflation, 2),  # Fiyat ağırlıklı
        'tuik_inflation': round(tuik_inflation, 2),  # TÜİK metodolojisi
        'ito_inflation': round(ito_inflation, 2),  # İTO metodolojisi
        'period_days': days,
        'start_date': start_date,
        'end_date': end_date,
        'product_count': len(products),
        'top_increases': top_increases,
        'top_decreases': top_decreases,
        'all_products': products.to_dict('records'),
        'category_breakdown': advanced_result.category_breakdown if advanced_result.success else {}
    }


def compare_inflation_vs_stock(ticker: str, days: int = 30) -> Dict:
    """
    Kişisel enflasyonu hisse getirisiyle karşılaştırır.
    
    Args:
        ticker: Hisse kodu (THYAO, AAPL vs.)
        days: Karşılaştırma periyodu
    
    Returns:
        Detaylı karşılaştırma sonuçları
    """
    # Kişisel enflasyonu hesapla
    inflation_data = calculate_personal_inflation(days=days)
    
    if not inflation_data['success']:
        return {
            'success': False,
            'error': inflation_data.get('error', 'Enflasyon hesaplanamadı')
        }
    
    # Hisse analizini yap
    stock_data = analyze_stock(ticker, period="3mo")  # En az 3 aylık veri
    
    if not stock_data['success']:
        return {
            'success': False,
            'error': stock_data.get('error', 'Hisse verisi alınamadı')
        }
    
    # Hissenin belirtilen dönemdeki getirisini hesapla
    df = stock_data['data']
    
    if len(df) < days:
        actual_days = len(df)
    else:
        actual_days = days
    
    # İlgili dönemin başlangıç ve bitiş fiyatları
    start_idx = max(0, len(df) - actual_days)
    start_price = df.iloc[start_idx]['Close']
    end_price = df.iloc[-1]['Close']
    
    stock_return = ((end_price - start_price) / start_price) * 100
    
    # Reel getiri hesapla
    personal_inflation = inflation_data['inflation']
    real_return = stock_return - personal_inflation
    
    # Yorum oluştur
    if real_return > 5:
        verdict = "🟢 KAZANÇ"
        comment = f"Bu hisse senin enflasyonunu rahatça yendi! Paranın değeri arttı."
        emoji = "🚀"
    elif real_return > 0:
        verdict = "🟢 KAZANÇ"
        comment = f"Bu hisse enflasyonu yendi ama fark küçük. Paranı korudun."
        emoji = "✅"
    elif real_return > -3:
        verdict = "🟡 NÖTR"
        comment = f"Hisse getirisi enflasyona yakın. Ne kazandın ne kaybettin."
        emoji = "➖"
    else:
        verdict = "🔴 KAYIP"
        comment = f"Bu hisse enflasyona yenildi. Paranın değeri eridi."
        emoji = "📉"
    
    # Yıllık projeksiyon
    daily_inflation = personal_inflation / days
    projected_yearly_inflation = daily_inflation * 365
    
    daily_stock_return = stock_return / actual_days
    projected_yearly_return = daily_stock_return * 252  # İşlem günü
    
    return {
        'success': True,
        'ticker': stock_data['ticker'],
        'period_days': actual_days,
        
        # Enflasyon verileri
        'personal_inflation': personal_inflation,
        'projected_yearly_inflation': round(projected_yearly_inflation, 1),
        'inflation_details': inflation_data,
        
        # Hisse verileri
        'stock_return': round(stock_return, 2),
        'projected_yearly_return': round(projected_yearly_return, 1),
        'current_price': stock_data['current_price'],
        'start_price': start_price,
        'rsi': stock_data['rsi'],
        'signal': stock_data['signals']['overall'],
        
        # Karşılaştırma
        'real_return': round(real_return, 2),
        'verdict': verdict,
        'comment': comment,
        'emoji': emoji,
        
        # İstatistikler
        'stats': {
            'inflation_start': inflation_data['start_date'],
            'inflation_end': inflation_data['end_date'],
            'product_count': inflation_data['product_count'],
            'top_inflated': inflation_data['top_increases'][:3] if inflation_data['top_increases'] else []
        }
    }


def multi_stock_comparison(tickers: list, days: int = 30) -> pd.DataFrame:
    """
    Birden fazla hisseyi kişisel enflasyonla karşılaştırır.
    """
    inflation_data = calculate_personal_inflation(days=days)
    
    if not inflation_data['success']:
        return pd.DataFrame()
    
    personal_inflation = inflation_data['inflation']
    
    results = []
    
    for ticker in tickers:
        stock_data = analyze_stock(ticker, period="3mo")
        
        if stock_data['success']:
            df = stock_data['data']
            actual_days = min(days, len(df))
            
            start_idx = max(0, len(df) - actual_days)
            start_price = df.iloc[start_idx]['Close']
            end_price = df.iloc[-1]['Close']
            
            stock_return = ((end_price - start_price) / start_price) * 100
            real_return = stock_return - personal_inflation
            
            if real_return > 0:
                verdict = "✅ Yendi"
            else:
                verdict = "❌ Yenildi"
            
            results.append({
                'Hisse': stock_data['ticker'],
                'Fiyat': round(end_price, 2),
                f'{actual_days}G Getiri %': round(stock_return, 2),
                'Enflasyon %': round(personal_inflation, 2),
                'Reel Getiri %': round(real_return, 2),
                'Sonuç': verdict,
                'RSI': round(stock_data['rsi'], 1) if stock_data['rsi'] else None,
                'Sinyal': stock_data['signals']['overall']
            })
    
    df = pd.DataFrame(results)
    
    if not df.empty:
        df = df.sort_values('Reel Getiri %', ascending=False)
    
    return df


def find_inflation_beaters(min_return: float = 0, days: int = 30) -> list:
    """
    Enflasyonu yenen BIST hisselerini bulur.
    """
    inflation_data = calculate_personal_inflation(days=days)
    
    if not inflation_data['success']:
        return []
    
    personal_inflation = inflation_data['inflation']
    
    # Popüler BIST hisseleri
    bist_tickers = [
        'THYAO', 'GARAN', 'AKBNK', 'TUPRS', 'EREGL', 'ASELS',
        'KCHOL', 'SAHOL', 'FROTO', 'SISE', 'TOASO', 'BIMAS',
        'MGROS', 'ARCLK', 'TCELL', 'ISCTR', 'SASA', 'PGSUS'
    ]
    
    beaters = []
    
    for ticker in bist_tickers:
        try:
            result = compare_inflation_vs_stock(ticker, days)
            if result['success'] and result['real_return'] >= min_return:
                beaters.append({
                    'ticker': result['ticker'],
                    'stock_return': result['stock_return'],
                    'real_return': result['real_return'],
                    'signal': result['signal'],
                    'price': result['current_price']
                })
        except:
            continue
    
    # Reel getiriye göre sırala
    beaters.sort(key=lambda x: x['real_return'], reverse=True)
    
    return beaters


def generate_recommendation(comparison: Dict) -> str:
    """Karşılaştırma sonucuna göre öneri üretir."""
    if not comparison.get('success'):
        return "Veri yetersiz, öneri üretilemiyor."
    
    real_return = comparison['real_return']
    rsi = comparison.get('rsi')
    signal = comparison.get('signal', 'Tut')
    
    recommendations = []
    
    # Reel getiri bazlı
    if real_return > 10:
        recommendations.append("🌟 Bu hisse enflasyonu ciddi şekilde yendi. Kâr realizasyonu düşünülebilir.")
    elif real_return > 5:
        recommendations.append("✅ İyi performans! Pozisyon tutulabilir.")
    elif real_return > 0:
        recommendations.append("👍 Enflasyonu yeniyor ama marj dar. Takipte kal.")
    elif real_return > -5:
        recommendations.append("⚠️ Enflasyona yakın performans. Alternatifler araştırılabilir.")
    else:
        recommendations.append("🚨 Bu hisse enflasyona karşı kaybettiriyor. Çıkış stratejisi düşün.")
    
    # RSI bazlı
    if rsi:
        if rsi < 30:
            recommendations.append(f"📊 RSI ({rsi:.0f}) aşırı satım bölgesinde. Alım fırsatı olabilir.")
        elif rsi > 70:
            recommendations.append(f"📊 RSI ({rsi:.0f}) aşırı alım bölgesinde. Dikkatli ol.")
    
    # Sinyal bazlı
    if 'Al' in signal:
        recommendations.append(f"📈 Teknik analiz sinyali: {signal}")
    elif 'Sat' in signal:
        recommendations.append(f"📉 Teknik analiz sinyali: {signal}")
    
    return "\n".join(recommendations)


if __name__ == '__main__':
    print("=" * 60)
    print("💰 Kişisel Enflasyon vs Hisse Getirisi Testi")
    print("=" * 60)
    
    # Kişisel enflasyonu hesapla
    inflation = calculate_personal_inflation(days=30)
    
    if inflation['success']:
        print(f"\n📊 Senin Market Enflasyonun (30 gün): %{inflation['inflation']:.2f}")
        print(f"   Ağırlıklı: %{inflation['weighted_inflation']:.2f}")
        print(f"   Ürün sayısı: {inflation['product_count']}")
        
        if inflation['top_increases']:
            print("\n   En çok artan ürünler:")
            for p in inflation['top_increases'][:3]:
                print(f"     • {p['product_name']}: %{p['change_pct']:.1f}")
    else:
        print(f"\n❌ {inflation.get('error', 'Hata')}")
    
    # Hisse karşılaştırması
    print("\n" + "=" * 60)
    comparison = compare_inflation_vs_stock("THYAO", days=30)
    
    if comparison['success']:
        print(f"\n📈 {comparison['ticker']} Karşılaştırması:")
        print(f"   Senin Enflasyonun: %{comparison['personal_inflation']:.2f}")
        print(f"   Hisse Getirisi: %{comparison['stock_return']:.2f}")
        print(f"   Reel Getiri: %{comparison['real_return']:.2f}")
        print(f"\n   {comparison['verdict']}")
        print(f"   {comparison['comment']}")
    else:
        print(f"\n❌ {comparison.get('error', 'Hata')}")
