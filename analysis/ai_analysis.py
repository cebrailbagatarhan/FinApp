"""
Yapay Zeka Destekli Piyasa Analiz Motoru
=========================================
Teknik indikatörleri, makro verileri ve piyasa koşullarını 
analiz ederek kapsamlı yatırım değerlendirmesi yapar.

Kullanılan Teknikler:
- Teknik analiz sinyalleri (RSI, MACD, Bollinger, Stochastic vb.)
- Destek/direnç analizi
- Momentum ve trend analizi
- Volatilite analizi
- Makro ekonomik korelasyonlar
- Sektörel karşılaştırma
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.stock_search import analyze_stock, fetch_stock_live, add_technical_indicators


# ============================================================================
# ANALİZ MOTORLARI
# ============================================================================

class AIMarketAnalyzer:
    """
    Yapay zeka destekli piyasa analiz motoru.
    Birden fazla veri kaynağını birleştirerek kapsamlı analiz sunar.
    """
    
    def __init__(self):
        self.analysis_cache = {}
    
    def full_analysis(self, ticker: str, period: str = "6mo") -> Dict:
        """
        Bir hisse için tam yapay zeka analizi yapar.
        
        Returns:
            Dict with comprehensive analysis results
        """
        # Temel hisse verisi
        stock_result = analyze_stock(ticker, period)
        
        if not stock_result['success']:
            return {
                'success': False,
                'error': stock_result.get('error', 'Veri alınamadı'),
                'ticker': ticker
            }
        
        df = stock_result['data']
        
        # Alt analizleri çalıştır
        trend_analysis = self._analyze_trend(df)
        momentum_analysis = self._analyze_momentum(df, stock_result)
        volatility_analysis = self._analyze_volatility(df)
        volume_analysis = self._analyze_volume(df)
        pattern_analysis = self._detect_patterns(df)
        risk_analysis = self._analyze_risk(df, stock_result)
        
        # Genel puan ve yorum oluştur
        overall_score = self._calculate_overall_score(
            trend_analysis, momentum_analysis, volatility_analysis,
            volume_analysis, pattern_analysis, risk_analysis
        )
        
        ai_commentary = self._generate_commentary(
            ticker=stock_result.get('ticker', ticker),
            stock_result=stock_result,
            trend=trend_analysis,
            momentum=momentum_analysis,
            volatility=volatility_analysis,
            volume=volume_analysis,
            patterns=pattern_analysis,
            risk=risk_analysis,
            score=overall_score
        )
        
        return {
            'success': True,
            'ticker': stock_result.get('ticker', ticker),
            'current_price': stock_result['current_price'],
            'last_update': stock_result.get('last_update', ''),
            
            # Alt analizler
            'trend': trend_analysis,
            'momentum': momentum_analysis,
            'volatility': volatility_analysis,
            'volume': volume_analysis,
            'patterns': pattern_analysis,
            'risk': risk_analysis,
            
            # Genel sonuç
            'overall_score': overall_score,
            'ai_commentary': ai_commentary,
            'signals': stock_result['signals'],
            'support_resistance': stock_result['support_resistance']
        }
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """Trend analizi - yön, güç, süre."""
        if len(df) < 20:
            return {'direction': 'Belirsiz', 'strength': 0, 'details': []}
        
        close = df['Close'].values
        
        # Kısa vadeli trend (20 gün)
        short_trend = (close[-1] - close[-min(20, len(close))]) / close[-min(20, len(close))] * 100
        
        # Orta vadeli trend (50 gün)
        mid_period = min(50, len(close))
        mid_trend = (close[-1] - close[-mid_period]) / close[-mid_period] * 100
        
        # Uzun vadeli trend (tüm dönem)
        long_trend = (close[-1] - close[0]) / close[0] * 100
        
        # SMA trend
        sma20 = df.get('SMA_20')
        sma50 = df.get('SMA_50')
        
        details = []
        score = 0
        
        # Kısa vadeli
        if short_trend > 5:
            details.append(f"📈 Kısa vadeli güçlü yükseliş trendi (%{short_trend:.1f})")
            score += 2
        elif short_trend > 0:
            details.append(f"📈 Kısa vadeli hafif yükseliş (%{short_trend:.1f})")
            score += 1
        elif short_trend > -5:
            details.append(f"📉 Kısa vadeli hafif düşüş (%{short_trend:.1f})")
            score -= 1
        else:
            details.append(f"📉 Kısa vadeli güçlü düşüş trendi (%{short_trend:.1f})")
            score -= 2
        
        # Orta vadeli
        if mid_trend > 10:
            details.append(f"📈 Orta vadeli güçlü trend (%{mid_trend:.1f})")
            score += 2
        elif mid_trend > 0:
            details.append(f"📈 Orta vadeli pozitif (%{mid_trend:.1f})")
            score += 1
        else:
            details.append(f"📉 Orta vadeli negatif (%{mid_trend:.1f})")
            score -= 1
        
        # SMA analizi
        if sma20 is not None and sma50 is not None:
            last_sma20 = sma20.iloc[-1] if pd.notna(sma20.iloc[-1]) else None
            last_sma50 = sma50.iloc[-1] if pd.notna(sma50.iloc[-1]) else None
            
            if last_sma20 and last_sma50:
                if last_sma20 > last_sma50:
                    details.append("🟢 Golden Cross aktif (SMA20 > SMA50)")
                    score += 1
                else:
                    details.append("🔴 Death Cross aktif (SMA20 < SMA50)")
                    score -= 1
                
                if close[-1] > last_sma20:
                    details.append("🟢 Fiyat 20 günlük ortalamanın üzerinde")
                    score += 1
                else:
                    details.append("🔴 Fiyat 20 günlük ortalamanın altında")
                    score -= 1
        
        # Yön belirle
        if score >= 3:
            direction = "Güçlü Yükseliş"
        elif score >= 1:
            direction = "Yükseliş"
        elif score <= -3:
            direction = "Güçlü Düşüş"
        elif score <= -1:
            direction = "Düşüş"
        else:
            direction = "Yatay"
        
        return {
            'direction': direction,
            'strength': score,
            'short_trend_pct': round(short_trend, 2),
            'mid_trend_pct': round(mid_trend, 2),
            'long_trend_pct': round(long_trend, 2),
            'details': details
        }
    
    def _analyze_momentum(self, df: pd.DataFrame, stock_result: Dict) -> Dict:
        """Momentum analizi - RSI, MACD, Stochastic."""
        details = []
        score = 0
        
        rsi = stock_result.get('rsi')
        macd_hist = stock_result.get('macd_hist')
        stoch_k = stock_result.get('stoch_k')
        stoch_d = stock_result.get('stoch_d')
        
        # RSI Analizi
        rsi_status = "Nötr"
        if rsi is not None and pd.notna(rsi):
            if rsi < 25:
                rsi_status = "Aşırı Satım (Dip Fırsatı)"
                details.append(f"🟢 RSI çok düşük ({rsi:.1f}) - potansiyel dip fırsatı")
                score += 3
            elif rsi < 35:
                rsi_status = "Satım Bölgesi"
                details.append(f"🟢 RSI düşük ({rsi:.1f}) - alım fırsatı olabilir")
                score += 2
            elif rsi > 75:
                rsi_status = "Aşırı Alım (Kâr Realizasyonu)"
                details.append(f"🔴 RSI çok yüksek ({rsi:.1f}) - aşırı alım, düzeltme riski")
                score -= 3
            elif rsi > 65:
                rsi_status = "Alım Bölgesi"
                details.append(f"🟡 RSI yüksek ({rsi:.1f}) - dikkatli olun")
                score -= 1
            else:
                rsi_status = "Nötr"
                details.append(f"⚪ RSI nötr bölgede ({rsi:.1f})")
        
        # MACD Analizi
        macd_status = "Nötr"
        if macd_hist is not None and pd.notna(macd_hist):
            # MACD histogram yönü
            if len(df) > 2 and 'MACD_Hist' in df.columns:
                last_3 = df['MACD_Hist'].tail(3).dropna().values
                if len(last_3) >= 2:
                    if last_3[-1] > last_3[-2] and macd_hist > 0:
                        macd_status = "Güçlü Pozitif"
                        details.append("🟢 MACD pozitif ve güçleniyor")
                        score += 2
                    elif macd_hist > 0:
                        macd_status = "Pozitif"
                        details.append("🟢 MACD pozitif")
                        score += 1
                    elif last_3[-1] < last_3[-2] and macd_hist < 0:
                        macd_status = "Güçlü Negatif"
                        details.append("🔴 MACD negatif ve zayıflıyor")
                        score -= 2
                    else:
                        macd_status = "Negatif"
                        details.append("🔴 MACD negatif")
                        score -= 1
        
        # Stochastic
        stoch_status = "Nötr"
        if stoch_k is not None and pd.notna(stoch_k):
            if stoch_k < 20:
                stoch_status = "Aşırı Satım"
                details.append(f"🟢 Stochastic aşırı satım ({stoch_k:.1f})")
                score += 1
            elif stoch_k > 80:
                stoch_status = "Aşırı Alım"
                details.append(f"🔴 Stochastic aşırı alım ({stoch_k:.1f})")
                score -= 1
        
        # Genel momentum durumu
        if score >= 3:
            overall = "Güçlü Pozitif Momentum"
        elif score >= 1:
            overall = "Pozitif Momentum"
        elif score <= -3:
            overall = "Güçlü Negatif Momentum"
        elif score <= -1:
            overall = "Negatif Momentum"
        else:
            overall = "Nötr"
        
        return {
            'overall': overall,
            'score': score,
            'rsi_status': rsi_status,
            'rsi_value': rsi,
            'macd_status': macd_status,
            'stoch_status': stoch_status,
            'details': details
        }
    
    def _analyze_volatility(self, df: pd.DataFrame) -> Dict:
        """Volatilite analizi - ATR, Bollinger Band genişliği."""
        details = []
        
        if len(df) < 20:
            return {'level': 'Belirsiz', 'atr_pct': 0, 'details': []}
        
        close = df['Close'].values
        
        # Günlük getiri standart sapması
        returns = pd.Series(close).pct_change().dropna()
        daily_vol = returns.std() * 100
        annualized_vol = daily_vol * np.sqrt(252)
        
        # ATR yüzdesi
        atr = df.get('ATR')
        atr_pct = 0
        if atr is not None and pd.notna(atr.iloc[-1]) and close[-1] > 0:
            atr_pct = (atr.iloc[-1] / close[-1]) * 100
        
        # Bollinger Band genişliği
        bb_high = df.get('BB_High')
        bb_low = df.get('BB_Low')
        bb_width_pct = 0
        if (bb_high is not None and bb_low is not None and 
            pd.notna(bb_high.iloc[-1]) and pd.notna(bb_low.iloc[-1]) and close[-1] > 0):
            bb_width_pct = ((bb_high.iloc[-1] - bb_low.iloc[-1]) / close[-1]) * 100
        
        # Seviye belirleme
        if annualized_vol > 60:
            level = "Çok Yüksek"
            details.append(f"🔴 Çok yüksek volatilite (%{annualized_vol:.0f} yıllık)")
            details.append("⚠️ Bu hisse çok dalgalı, yüksek risk taşıyor")
        elif annualized_vol > 40:
            level = "Yüksek"
            details.append(f"🟠 Yüksek volatilite (%{annualized_vol:.0f} yıllık)")
        elif annualized_vol > 20:
            level = "Orta"
            details.append(f"🟡 Orta volatilite (%{annualized_vol:.0f} yıllık)")
        else:
            level = "Düşük"
            details.append(f"🟢 Düşük volatilite (%{annualized_vol:.0f} yıllık)")
        
        if atr_pct > 0:
            details.append(f"📊 Günlük ATR: %{atr_pct:.2f} (ortalama günlük hareket aralığı)")
        
        if bb_width_pct > 0:
            if bb_width_pct > 15:
                details.append(f"📈 Bollinger bantları geniş (%{bb_width_pct:.1f}) - yüksek belirsizlik")
            elif bb_width_pct < 5:
                details.append(f"📉 Bollinger bantları dar (%{bb_width_pct:.1f}) - sıkışma, kırılma beklenebilir")
        
        return {
            'level': level,
            'daily_vol_pct': round(daily_vol, 2),
            'annualized_vol_pct': round(annualized_vol, 2),
            'atr_pct': round(atr_pct, 2),
            'bb_width_pct': round(bb_width_pct, 2),
            'details': details
        }
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict:
        """Hacim analizi."""
        details = []
        
        if 'Volume' not in df.columns or len(df) < 20:
            return {'trend': 'Belirsiz', 'details': []}
        
        vol = df['Volume'].values
        avg_vol_20 = np.mean(vol[-20:])
        last_vol = vol[-1]
        
        if avg_vol_20 > 0:
            vol_ratio = last_vol / avg_vol_20
            
            if vol_ratio > 2:
                details.append(f"🔴 Hacim çok yüksek (ortalamanın {vol_ratio:.1f}x katı) - büyük ilgi/haber")
            elif vol_ratio > 1.3:
                details.append(f"📈 Hacim ortalamanın üzerinde ({vol_ratio:.1f}x)")
            elif vol_ratio < 0.5:
                details.append(f"📉 Hacim çok düşük ({vol_ratio:.1f}x) - ilgi az")
            else:
                details.append(f"📊 Normal hacim ({vol_ratio:.1f}x ortalama)")
            
            # Hacim trendi
            vol_5d = np.mean(vol[-5:]) if len(vol) >= 5 else last_vol
            vol_20d = np.mean(vol[-20:])
            
            if vol_5d > vol_20d * 1.2:
                details.append("📈 Son 5 günde hacim artıyor - artan ilgi")
                trend = "Artıyor"
            elif vol_5d < vol_20d * 0.8:
                details.append("📉 Son 5 günde hacim azalıyor")
                trend = "Azalıyor"
            else:
                trend = "Stabil"
        else:
            trend = "Belirsiz"
            vol_ratio = 0
        
        return {
            'trend': trend,
            'last_volume': int(last_vol) if last_vol else 0,
            'avg_volume_20d': int(avg_vol_20) if avg_vol_20 else 0,
            'volume_ratio': round(vol_ratio, 2) if vol_ratio else 0,
            'details': details
        }
    
    def _detect_patterns(self, df: pd.DataFrame) -> Dict:
        """Grafik formasyonları ve trend kırılımları tespit eder."""
        details = []
        
        if len(df) < 20:
            return {'patterns': [], 'details': []}
        
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        
        patterns = []
        
        # Double Bottom (Çift Dip)
        if len(close) >= 30:
            last_30 = close[-30:]
            min_idx = np.argmin(last_30)
            
            # İlk 15 günde ve son 15 günde birer dip var mı?
            first_half_min = np.min(last_30[:15])
            second_half_min = np.min(last_30[15:])
            mid_max = np.max(last_30[10:20])
            
            if (abs(first_half_min - second_half_min) / first_half_min < 0.03 and
                mid_max > first_half_min * 1.03):
                patterns.append("Çift Dip (Double Bottom)")
                details.append("🟢 Çift dip formasyonu tespit edildi - yukarı kırılma potansiyeli")
        
        # Bollinger Squeeze (Sıkışma)
        if 'BB_High' in df.columns and 'BB_Low' in df.columns:
            bb_h = df['BB_High'].dropna().values
            bb_l = df['BB_Low'].dropna().values
            if len(bb_h) >= 20:
                bb_width = bb_h - bb_l
                recent_width = np.mean(bb_width[-5:])
                past_width = np.mean(bb_width[-20:-5])
                
                if past_width > 0 and recent_width / past_width < 0.7:
                    patterns.append("Bollinger Sıkışması")
                    details.append("⚡ Bollinger sıkışması - yakında sert hareket bekleniyor")
        
        # RSI Diverjans
        if 'RSI' in df.columns and len(df) >= 14:
            rsi_vals = df['RSI'].dropna().values
            close_recent = close[-len(rsi_vals):]
            
            if len(rsi_vals) >= 14:
                # Fiyat yeni dip yaparken RSI yapmıyorsa: pozitif diverjans
                if (close_recent[-1] < close_recent[-7] and 
                    rsi_vals[-1] > rsi_vals[-7]):
                    patterns.append("Pozitif Diverjans (RSI)")
                    details.append("🟢 RSI pozitif diverjans - fiyat düşerken momentum artıyor")
                
                # Fiyat yeni tepe yaparken RSI yapmıyorsa: negatif diverjans
                if (close_recent[-1] > close_recent[-7] and 
                    rsi_vals[-1] < rsi_vals[-7]):
                    patterns.append("Negatif Diverjans (RSI)")
                    details.append("🔴 RSI negatif diverjans - fiyat yükselirken momentum azalıyor")
        
        # Üst üste artış/düşüş günleri
        if len(close) >= 5:
            consecutive_up = 0
            consecutive_down = 0
            for i in range(-1, -6, -1):
                if close[i] > close[i-1]:
                    consecutive_up += 1
                else:
                    break
            for i in range(-1, -6, -1):
                if close[i] < close[i-1]:
                    consecutive_down += 1
                else:
                    break
            
            if consecutive_up >= 4:
                patterns.append(f"{consecutive_up} Gün Üst Üste Yükseliş")
                details.append(f"📈 {consecutive_up} gün üst üste yükseliş - momentumlu ama dikkat")
            if consecutive_down >= 4:
                patterns.append(f"{consecutive_down} Gün Üst Üste Düşüş")
                details.append(f"📉 {consecutive_down} gün üst üste düşüş - dip fırsatı olabilir")
        
        return {
            'patterns': patterns,
            'details': details
        }
    
    def _analyze_risk(self, df: pd.DataFrame, stock_result: Dict) -> Dict:
        """Risk değerlendirmesi."""
        details = []
        risk_score = 5  # 1-10 arası (1=düşük, 10=yüksek)
        
        close = df['Close'].values
        
        # Drawdown analizi
        peak = np.maximum.accumulate(close)
        drawdown = (close - peak) / peak * 100
        max_drawdown = drawdown.min()
        current_drawdown = drawdown[-1]
        
        if max_drawdown < -30:
            details.append(f"🔴 Maksimum düşüş çok yüksek (%{max_drawdown:.1f})")
            risk_score += 2
        elif max_drawdown < -15:
            details.append(f"🟠 Önemli düşüş yaşanmış (%{max_drawdown:.1f})")
            risk_score += 1
        
        if current_drawdown < -15:
            details.append(f"📉 Hisse tepeden %{current_drawdown:.1f} geride")
            risk_score += 1
        elif current_drawdown > -3:
            details.append(f"📈 Hisse tepeye yakın (%{current_drawdown:.1f})")
        
        # Volatilite riski
        returns = pd.Series(close).pct_change().dropna()
        daily_vol = returns.std() * 100
        
        if daily_vol > 4:
            risk_score += 2
            details.append("⚠️ Günlük dalgalanma çok yüksek")
        elif daily_vol > 2.5:
            risk_score += 1
        
        # RSI aşırılık riski
        rsi = stock_result.get('rsi')
        if rsi is not None:
            if rsi > 75:
                risk_score += 1
                details.append("⚠️ RSI aşırı alım - düzeltme riski")
            elif rsi < 25:
                details.append("💡 RSI dipte - risk/getiri oranı olumlu olabilir")
        
        risk_score = min(10, max(1, risk_score))
        
        if risk_score >= 8:
            level = "Çok Yüksek"
        elif risk_score >= 6:
            level = "Yüksek"
        elif risk_score >= 4:
            level = "Orta"
        else:
            level = "Düşük"
        
        return {
            'level': level,
            'score': risk_score,
            'max_drawdown_pct': round(max_drawdown, 2),
            'current_drawdown_pct': round(current_drawdown, 2),
            'details': details
        }
    
    def _calculate_overall_score(self, trend, momentum, volatility, 
                                  volume, patterns, risk) -> Dict:
        """Tüm alt analizlerden genel puan hesaplar (0-100)."""
        score = 50  # Başlangıç
        
        # Trend katkısı (+/- 20)
        trend_score = trend.get('strength', 0)
        score += min(20, max(-20, trend_score * 4))
        
        # Momentum katkısı (+/- 15)
        mom_score = momentum.get('score', 0)
        score += min(15, max(-15, mom_score * 3))
        
        # Volatilite (yüksek volatilite = risk)
        vol_level = volatility.get('level', 'Orta')
        vol_map = {'Düşük': 5, 'Orta': 0, 'Yüksek': -5, 'Çok Yüksek': -10}
        score += vol_map.get(vol_level, 0)
        
        # Pattern katkısı
        pattern_details = patterns.get('details', [])
        for d in pattern_details:
            if '🟢' in d:
                score += 3
            elif '🔴' in d:
                score -= 3
        
        # Risk düzeltmesi
        risk_score = risk.get('score', 5)
        if risk_score >= 8:
            score -= 10
        elif risk_score >= 6:
            score -= 5
        elif risk_score <= 3:
            score += 5
        
        score = min(100, max(0, score))
        
        if score >= 75:
            label = "Güçlü Al"
            color = "green"
        elif score >= 60:
            label = "Al"
            color = "lightgreen"
        elif score >= 45:
            label = "Nötr"
            color = "gray"
        elif score >= 30:
            label = "Sat"
            color = "orange"
        else:
            label = "Güçlü Sat"
            color = "red"
        
        return {
            'score': round(score),
            'label': label,
            'color': color
        }
    
    def _generate_commentary(self, ticker, stock_result, trend, momentum,
                              volatility, volume, patterns, risk, score) -> str:
        """Kapsamlı AI yorumu oluşturur."""
        parts = []
        
        price = stock_result['current_price']
        
        # Başlık
        parts.append(f"## 🤖 {ticker} Yapay Zeka Analiz Raporu")
        parts.append(f"**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        parts.append(f"**Fiyat:** {price:.2f}")
        parts.append(f"**Genel Puan:** {score['score']}/100 ({score['label']})")
        parts.append("")
        
        # Trend
        parts.append("### 📈 Trend Analizi")
        parts.append(f"**Yön:** {trend['direction']}")
        if trend.get('short_trend_pct') is not None:
            parts.append(f"- Kısa vadeli: %{trend['short_trend_pct']:.1f}")
        if trend.get('mid_trend_pct') is not None:
            parts.append(f"- Orta vadeli: %{trend['mid_trend_pct']:.1f}")
        for d in trend.get('details', [])[-3:]:
            parts.append(f"- {d}")
        parts.append("")
        
        # Momentum
        parts.append("### ⚡ Momentum")
        parts.append(f"**Durum:** {momentum['overall']}")
        for d in momentum.get('details', [])[-4:]:
            parts.append(f"- {d}")
        parts.append("")
        
        # Risk
        parts.append("### ⚠️ Risk Değerlendirmesi")
        parts.append(f"**Risk Seviyesi:** {risk['level']} ({risk['score']}/10)")
        parts.append(f"- Maksimum düşüş: %{risk['max_drawdown_pct']:.1f}")
        for d in risk.get('details', [])[-3:]:
            parts.append(f"- {d}")
        parts.append("")
        
        # Formasyonlar
        if patterns.get('patterns'):
            parts.append("### 🔍 Tespit Edilen Formasyonlar")
            for p in patterns['patterns']:
                parts.append(f"- **{p}**")
            for d in patterns.get('details', []):
                parts.append(f"- {d}")
            parts.append("")
        
        # Sonuç ve öneri
        parts.append("### 💡 Sonuç ve Öneri")
        
        s = score['score']
        if s >= 75:
            parts.append("✅ **Güçlü alım sinyali.** Trend, momentum ve teknik göstergeler olumlu. "
                        "Kademeli alım stratejisi uygulanabilir. Stop-loss seviyesi destek noktasına koyulmalı.")
        elif s >= 60:
            parts.append("🟢 **Alım yönünde.** Genel görünüm pozitif ancak bazı riskler mevcut. "
                        "Pozisyon küçük tutularak giriş yapılabilir.")
        elif s >= 45:
            parts.append("⚪ **Nötr bölge.** Net bir sinyal yok. Mevcut pozisyonlar tutulabilir, "
                        "yeni giriş için daha net sinyal beklenebilir.")
        elif s >= 30:
            parts.append("🟠 **Dikkatli olun.** Olumsuz sinyaller beliriyor. "
                        "Stop-loss sıkılaştırılmalı, yeni alımdan kaçınılmalı.")
        else:
            parts.append("🔴 **Satış sinyali.** Trend ve momentum olumsuz. "
                        "Açık pozisyon varsa küçültme veya kâr/zarar realizasyonu düşünülmeli.")
        
        parts.append("")
        parts.append("*⚠️ Bu analiz yatırım tavsiyesi değildir. Kendi araştırmanızı yapın.*")
        
        return "\n".join(parts)


def compare_stocks_ai(tickers: List[str], period: str = "6mo") -> pd.DataFrame:
    """Birden fazla hisseyi AI puanlamasıyla karşılaştırır."""
    analyzer = AIMarketAnalyzer()
    results = []
    
    for ticker in tickers:
        analysis = analyzer.full_analysis(ticker, period)
        if analysis['success']:
            results.append({
                'Hisse': analysis['ticker'],
                'Fiyat': round(analysis['current_price'], 2),
                'AI Puan': analysis['overall_score']['score'],
                'Sinyal': analysis['overall_score']['label'],
                'Trend': analysis['trend']['direction'],
                'Momentum': analysis['momentum']['overall'],
                'Risk': analysis['risk']['level'],
                'Volatilite': analysis['volatility']['level']
            })
    
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('AI Puan', ascending=False)
    return df


def render_ai_analysis_tab():
    """Streamlit'te AI analiz sekmesini render eder."""
    import streamlit as st
    import plotly.graph_objects as go
    
    st.markdown("## 🤖 Yapay Zeka Destekli Analiz")
    st.markdown("*Teknik göstergeleri, formasyonları ve risk faktörlerini birleştiren kapsamlı analiz*")
    st.markdown("---")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        ticker_input = st.text_input(
            "🔍 Hisse Kodu",
            placeholder="Örn: THYAO, ASELS, AAPL",
            key="ai_analysis_ticker"
        )
    
    with col2:
        analyze_btn = st.button("🤖 AI Analiz", type="primary", use_container_width=True)
    
    if analyze_btn and ticker_input:
        analyzer = AIMarketAnalyzer()
        
        with st.spinner(f"🤖 {ticker_input} için AI analiz yapılıyor..."):
            result = analyzer.full_analysis(ticker_input)
        
        if not result['success']:
            st.error(f"❌ {result.get('error', 'Analiz yapılamadı')}")
            return
        
        # Genel Puan
        score = result['overall_score']
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); 
                        padding: 2rem; border-radius: 15px; text-align: center; color: white;">
                <h3>🤖 AI Puan</h3>
                <h1 style="font-size: 3rem; margin: 0;">{score['score']}/100</h1>
                <p style="font-size: 1.3rem; margin-top: 0.5rem;">{score['label']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.metric("💰 Fiyat", f"{result['current_price']:.2f}")
            st.metric("📈 Trend", result['trend']['direction'])
        
        with col3:
            st.metric("⚡ Momentum", result['momentum']['overall'])
            st.metric("⚠️ Risk", f"{result['risk']['level']} ({result['risk']['score']}/10)")
        
        st.markdown("---")
        
        # AI Yorumu
        st.markdown(result['ai_commentary'])
        
        st.markdown("---")
        
        # Detaylı analiz tabları
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Trend", "⚡ Momentum", "📊 Volatilite", "🔍 Formasyonlar"
        ])
        
        with tab1:
            for d in result['trend'].get('details', []):
                st.markdown(f"- {d}")
        
        with tab2:
            for d in result['momentum'].get('details', []):
                st.markdown(f"- {d}")
        
        with tab3:
            for d in result['volatility'].get('details', []):
                st.markdown(f"- {d}")
            for d in result['volume'].get('details', []):
                st.markdown(f"- {d}")
        
        with tab4:
            if result['patterns'].get('patterns'):
                for p in result['patterns']['patterns']:
                    st.markdown(f"**{p}**")
                for d in result['patterns'].get('details', []):
                    st.markdown(f"- {d}")
            else:
                st.info("Şu an belirgin bir formasyon tespit edilmedi.")
    
    # Çoklu karşılaştırma
    st.markdown("---")
    st.markdown("### 📊 AI ile Hisse Karşılaştırma")
    
    multi_input = st.text_input(
        "Karşılaştırmak istediğiniz hisseleri virgülle yazın",
        placeholder="THYAO, GARAN, ASELS, KCHOL, TUPRS",
        key="ai_multi_compare"
    )
    
    if st.button("🤖 Hepsini Analiz Et", key="ai_multi_btn"):
        tickers = [t.strip() for t in multi_input.split(",") if t.strip()]
        if tickers:
            with st.spinner(f"🤖 {len(tickers)} hisse analiz ediliyor..."):
                comparison_df = compare_stocks_ai(tickers)
            
            if not comparison_df.empty:
                st.dataframe(comparison_df, use_container_width=True, hide_index=True)
                
                import plotly.express as px
                fig = px.bar(
                    comparison_df,
                    x='Hisse',
                    y='AI Puan',
                    color='AI Puan',
                    color_continuous_scale=['red', 'yellow', 'green'],
                    title='AI Puanlama Karşılaştırması'
                )
                fig.add_hline(y=50, line_dash="dash", line_color="gray",
                             annotation_text="Nötr Seviye")
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 AI Piyasa Analiz Motoru Test")
    print("=" * 60)
    
    analyzer = AIMarketAnalyzer()
    
    test_tickers = ['THYAO', 'ASELS']
    for ticker in test_tickers:
        print(f"\n📈 {ticker} analiz ediliyor...")
        result = analyzer.full_analysis(ticker, "6mo")
        
        if result['success']:
            score = result['overall_score']
            print(f"  AI Puan: {score['score']}/100 ({score['label']})")
            print(f"  Trend: {result['trend']['direction']}")
            print(f"  Momentum: {result['momentum']['overall']}")
            print(f"  Risk: {result['risk']['level']}")
        else:
            print(f"  ❌ {result.get('error')}")
    
    print("\n✅ Test tamamlandı!")
