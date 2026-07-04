"""
Sinyal Üretim Modülü
- RSI, MACD ve enflasyon verilerine göre al/sat sinyalleri
- Kombine analiz stratejisi
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, insert_signal
from analysis.inflation_calc import compare_inflation


def get_latest_stock_indicators(ticker: str = None) -> pd.DataFrame:
    """En son hisse indikatörlerini getirir."""
    conn = get_connection()
    
    if ticker:
        query = """
            SELECT ticker, date, close_price, rsi_value, macd_value, macd_signal, signal
            FROM stocks
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT 1
        """
        df = pd.read_sql_query(query, conn, params=(ticker,))
    else:
        query = """
            SELECT s1.*
            FROM stocks s1
            INNER JOIN (
                SELECT ticker, MAX(date) as max_date
                FROM stocks
                GROUP BY ticker
            ) s2 ON s1.ticker = s2.ticker AND s1.date = s2.max_date
        """
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    return df


def analyze_stock_signal(ticker: str) -> dict:
    """
    Tek bir hisse için detaylı sinyal analizi.
    """
    df = get_latest_stock_indicators(ticker)
    
    if df.empty:
        return {
            'ticker': ticker,
            'signal': 'No Data',
            'strength': 'N/A',
            'reasons': ['Veri bulunamadı']
        }
    
    row = df.iloc[0]
    rsi = row['rsi_value']
    macd = row['macd_value']
    macd_sig = row['macd_signal']
    price = row['close_price']
    
    reasons = []
    buy_score = 0
    sell_score = 0
    
    # RSI Analizi
    if pd.notna(rsi):
        if rsi < 30:
            reasons.append(f"RSI aşırı satım bölgesinde ({rsi:.1f})")
            buy_score += 2
        elif rsi < 40:
            reasons.append(f"RSI düşük ({rsi:.1f})")
            buy_score += 1
        elif rsi > 70:
            reasons.append(f"RSI aşırı alım bölgesinde ({rsi:.1f})")
            sell_score += 2
        elif rsi > 60:
            reasons.append(f"RSI yüksek ({rsi:.1f})")
            sell_score += 1
        else:
            reasons.append(f"RSI nötr ({rsi:.1f})")
    
    # MACD Analizi
    if pd.notna(macd) and pd.notna(macd_sig):
        macd_diff = macd - macd_sig
        if macd_diff > 0:
            reasons.append("MACD pozitif momentum")
            buy_score += 1
        else:
            reasons.append("MACD negatif momentum")
            sell_score += 1
    
    # Sinyal belirleme
    if buy_score >= 3:
        signal = "Strong Buy"
        strength = "Güçlü"
    elif buy_score >= 2:
        signal = "Buy"
        strength = "Orta"
    elif sell_score >= 3:
        signal = "Strong Sell"
        strength = "Güçlü"
    elif sell_score >= 2:
        signal = "Sell"
        strength = "Orta"
    else:
        signal = "Hold"
        strength = "Zayıf"
    
    return {
        'ticker': ticker,
        'price': price,
        'rsi': rsi,
        'macd': macd,
        'signal': signal,
        'strength': strength,
        'reasons': reasons,
        'buy_score': buy_score,
        'sell_score': sell_score
    }


def generate_combined_signals(country: str = "TR") -> list:
    """
    Enflasyon verisiyle kombine edilmiş al/sat sinyalleri üretir.
    
    Strateji:
    - Market Enflasyonu > Resmi Enflasyon VE RSI < 30 → Güçlü Al
    - Market Enflasyonu < Resmi Enflasyon VE RSI > 70 → Güçlü Sat
    """
    # Enflasyon karşılaştırması
    inflation_data = compare_inflation(country=country, days=30)
    inflation_difference = inflation_data['difference']
    
    # Tüm hisseleri analiz et
    stocks_df = get_latest_stock_indicators()
    
    signals = []
    
    for _, row in stocks_df.iterrows():
        ticker = row['ticker']
        rsi = row['rsi_value']
        price = row['close_price']
        basic_signal = row['signal']
        
        reasons = []
        final_signal = basic_signal
        signal_strength = "Normal"
        
        # Enflasyon + RSI kombine stratejisi
        if pd.notna(rsi):
            # Yüksek enflasyon + Düşük RSI = Güçlü Al
            if inflation_difference > 2 and rsi < 30:
                final_signal = "Strong Buy"
                signal_strength = "Güçlü"
                reasons.append(f"Market enflasyonu yüksek (+{inflation_difference:.1f}%)")
                reasons.append(f"RSI aşırı satım ({rsi:.1f})")
                reasons.append("Enflasyon hedge stratejisi aktif")
            
            # Yüksek enflasyon + Orta RSI = Al
            elif inflation_difference > 2 and rsi < 50:
                final_signal = "Buy"
                signal_strength = "Orta"
                reasons.append(f"Market enflasyonu yüksek (+{inflation_difference:.1f}%)")
                reasons.append("Enflasyona karşı hisse alımı öneriliyor")
            
            # Düşük enflasyon + Yüksek RSI = Sat
            elif inflation_difference < -2 and rsi > 70:
                final_signal = "Strong Sell"
                signal_strength = "Güçlü"
                reasons.append(f"Market enflasyonu düşük ({inflation_difference:.1f}%)")
                reasons.append(f"RSI aşırı alım ({rsi:.1f})")
            
            # Normal durum
            else:
                if rsi < 30:
                    reasons.append(f"RSI düşük ({rsi:.1f})")
                elif rsi > 70:
                    reasons.append(f"RSI yüksek ({rsi:.1f})")
                else:
                    reasons.append(f"RSI normal ({rsi:.1f})")
        
        signal_data = {
            'ticker': ticker,
            'price': price,
            'rsi': rsi,
            'basic_signal': basic_signal,
            'combined_signal': final_signal,
            'signal_strength': signal_strength,
            'reasons': reasons,
            'inflation_impact': inflation_difference
        }
        
        signals.append(signal_data)
        
        # Güçlü sinyalleri veritabanına kaydet
        if final_signal in ['Strong Buy', 'Strong Sell']:
            insert_signal(
                ticker=ticker,
                signal_type=final_signal,
                signal_strength=signal_strength,
                reason='; '.join(reasons),
                price_at_signal=price
            )
    
    return signals


def get_buy_recommendations(min_strength: str = "Normal") -> pd.DataFrame:
    """
    Al önerilerini güce göre filtreler.
    """
    signals = generate_combined_signals()
    
    strength_order = {"Zayıf": 1, "Normal": 2, "Orta": 3, "Güçlü": 4}
    min_strength_value = strength_order.get(min_strength, 2)
    
    buy_signals = [
        s for s in signals 
        if 'Buy' in s['combined_signal'] 
        and strength_order.get(s['signal_strength'], 0) >= min_strength_value
    ]
    
    if not buy_signals:
        return pd.DataFrame()
    
    df = pd.DataFrame(buy_signals)
    df = df.sort_values('signal_strength', ascending=False, 
                        key=lambda x: x.map(strength_order))
    
    return df[['ticker', 'price', 'rsi', 'combined_signal', 'signal_strength', 'reasons']]


def get_signal_summary() -> dict:
    """Genel sinyal özeti döndürür."""
    signals = generate_combined_signals()
    
    summary = {
        'total_stocks': len(signals),
        'strong_buy': len([s for s in signals if s['combined_signal'] == 'Strong Buy']),
        'buy': len([s for s in signals if s['combined_signal'] == 'Buy']),
        'hold': len([s for s in signals if s['combined_signal'] == 'Hold']),
        'sell': len([s for s in signals if s['combined_signal'] == 'Sell']),
        'strong_sell': len([s for s in signals if s['combined_signal'] == 'Strong Sell']),
        'signals': signals
    }
    
    return summary


if __name__ == '__main__':
    print("=" * 60)
    print("📊 Sinyal Analizi")
    print("=" * 60)
    
    # Özet
    summary = get_signal_summary()
    print(f"\n📈 Toplam Hisse: {summary['total_stocks']}")
    print(f"  🟢 Güçlü Al: {summary['strong_buy']}")
    print(f"  🟢 Al: {summary['buy']}")
    print(f"  🟡 Tut: {summary['hold']}")
    print(f"  🔴 Sat: {summary['sell']}")
    print(f"  🔴 Güçlü Sat: {summary['strong_sell']}")
    
    # Al önerileri
    print("\n" + "=" * 60)
    print("💡 Al Önerileri:")
    print("=" * 60)
    
    recommendations = get_buy_recommendations(min_strength="Orta")
    if not recommendations.empty:
        for _, row in recommendations.iterrows():
            print(f"\n{row['ticker']}")
            print(f"  Fiyat: {row['price']:.2f}")
            print(f"  RSI: {row['rsi']:.1f}")
            print(f"  Sinyal: {row['combined_signal']} ({row['signal_strength']})")
            print(f"  Sebepler: {', '.join(row['reasons'])}")
    else:
        print("Şu an güçlü al önerisi bulunmuyor.")
