"""
FinApp v4.0 - Profesyonel Finansal Analiz Platformu
- Investing.com kalitesinde ekonomik takvim
- Gerçek TÜİK TÜFE verileri
- Gelişmiş teknik analiz
- AI-destekli piyasa analizi
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_connection
from analysis.data_freshness import get_market_data_freshness
from analysis.inflation_calc import calculate_basket_inflation, compare_inflation
from analysis.stock_search import analyze_stock, search_stocks, compare_stocks
from analysis.calculator import (
    InflationCalculator, 
    TUIK_WEIGHTS, 
    ITO_WEIGHTS,
    get_category_for_product,
    export_weights_to_json
)
from analysis.personal_comparison import (
    calculate_personal_inflation,
    compare_inflation_vs_stock,
    multi_stock_comparison,
    find_inflation_beaters,
    generate_recommendation
)
from analysis.weights_config import (
    TUIK_WEIGHTS_2025,
    ITO_WEIGHTS_2025,
    WeightedInflationCalculator,
    get_simple_weights
)
from analysis.macro_visualization import MacroVisualizer, render_macro_analysis_tab
from scrapers.evds_data import (
    get_evds_inflation_data,
    save_evds_data_to_csv,
    load_evds_data_from_csv,
    generate_simulated_evds_data
)
from scrapers.economic_calendar import (
    get_economic_calendar,
    highlight_today_events,
    render_economic_calendar_tab,
    get_upcoming_high_importance_events
)
from analysis.ai_analysis import render_ai_analysis_tab, AIMarketAnalyzer
from scrapers.news_feed import render_news_tab, get_latest_news, get_market_summary_from_news

# Sayfa yapılandırması
st.set_page_config(
    page_title="FinApp - Kişisel Finans Analizi",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Profesyonel finans uygulaması teması
st.markdown("""
<style>
    /* Ana tema renkleri */
    :root {
        --primary: #1a73e8;
        --success: #0ecb81;
        --danger: #f6465d;
        --warning: #f0b90b;
        --bg-dark: #0b0e11;
        --bg-card: #1e2329;
        --text-primary: #eaecef;
        --text-secondary: #848e9c;
        --border: #2b3139;
    }
    
    /* Genel stil */
    .stApp { background-color: #0b0e11; }
    
    /* Header */
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #1a73e8, #0ecb81);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 0.5rem 0;
        margin-bottom: 0;
    }
    
    /* Kart stilleri */
    .metric-card {
        background: linear-gradient(135deg, #1e2329, #252a30);
        border: 1px solid #2b3139;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.3rem 0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(26, 115, 232, 0.15);
    }
    .metric-card h4 {
        color: #848e9c;
        font-size: 0.85rem;
        margin-bottom: 0.3rem;
        font-weight: 500;
    }
    .metric-card .value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #eaecef;
    }
    .metric-card .change-up { color: #0ecb81; font-weight: 600; }
    .metric-card .change-down { color: #f6465d; font-weight: 600; }
    
    /* Fiyat stilleri */
    .price-up { color: #0ecb81 !important; }
    .price-down { color: #f6465d !important; }
    .price-neutral { color: #f0b90b !important; }
    
    /* Sinyal badge'leri */
    .signal-buy {
        background: rgba(14, 203, 129, 0.15);
        color: #0ecb81;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        border: 1px solid rgba(14, 203, 129, 0.3);
        display: inline-block;
    }
    .signal-sell {
        background: rgba(246, 70, 93, 0.15);
        color: #f6465d;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        border: 1px solid rgba(246, 70, 93, 0.3);
        display: inline-block;
    }
    .signal-hold {
        background: rgba(240, 185, 11, 0.15);
        color: #f0b90b;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        border: 1px solid rgba(240, 185, 11, 0.3);
        display: inline-block;
    }
    
    /* Info box */
    .info-box {
        background: #1e2329;
        border: 1px solid #2b3139;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Verdict boxes */
    .verdict-win {
        background: rgba(14, 203, 129, 0.08);
        border-left: 4px solid #0ecb81;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
    }
    .verdict-lose {
        background: rgba(246, 70, 93, 0.08);
        border-left: 4px solid #f6465d;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
    }
    
    /* Tablo stilleri */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #1e2329;
        border-right: 1px solid #2b3139;
    }
    [data-testid="stSidebar"] .stRadio label {
        padding: 0.4rem 0;
    }
    
    /* Tab stilleri */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #1e2329;
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
    }
    
    /* Button */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    
    /* Divider */
    hr { border-color: #2b3139 !important; }
    
    /* Metric düzeltmesi */
    [data-testid="stMetricValue"] { font-size: 1.3rem; }
    [data-testid="stMetricDelta"] { font-size: 0.9rem; }
    
    .search-box { font-size: 1.1rem; }
    
    /* Ekonomik takvim satır vurgusu */
    .calendar-today {
        background: rgba(26, 115, 232, 0.1);
        border-left: 3px solid #1a73e8;
        padding: 0.5rem;
        border-radius: 0 6px 6px 0;
        margin: 2px 0;
    }
    .calendar-high {
        border-left: 3px solid #f6465d;
    }
    
    /* Küçük etiketler */
    .tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .tag-api { background: rgba(14, 203, 129, 0.15); color: #0ecb81; }
    .tag-cache { background: rgba(240, 185, 11, 0.15); color: #f0b90b; }
    .tag-ref { background: rgba(132, 142, 156, 0.15); color: #848e9c; }
</style>
""", unsafe_allow_html=True)


def init_data():
    """Veritabanını başlatır."""
    init_database()


# ==================== ANA SAYFA ====================
def show_home_page():
    """Ana sayfa - Profesyonel piyasa dashboard'u"""
    st.markdown('<h1 class="main-header">📊 FinApp - Finansal Analiz Platformu</h1>', unsafe_allow_html=True)
    st.caption(f"Son güncelleme: {datetime.now().strftime('%d.%m.%Y %H:%M')} • Veriler bilgilendirme amaçlıdır")
    
    # ─── HIZLI ARAMA ───
    col1, col2 = st.columns([4, 1])
    with col1:
        quick_ticker = st.text_input(
            "🔍 Hisse Ara",
            placeholder="Hisse kodu yazın (THYAO, ASELS, AAPL...)",
            key="home_search", label_visibility="collapsed"
        )
    with col2:
        search_btn = st.button("Analiz Et", type="primary", width='stretch')
    
    if search_btn and quick_ticker:
        with st.spinner(f"📊 {quick_ticker.upper()} analiz ediliyor..."):
            result = analyze_stock(quick_ticker)
            if result['success']:
                chg = result.get('change_1d', 0) or 0
                chg_class = 'change-up' if chg >= 0 else 'change-down'
                chg_icon = '▲' if chg >= 0 else '▼'
                signal = result['signals']['overall']
                sig_class = 'signal-buy' if 'Al' in signal else 'signal-sell' if 'Sat' in signal else 'signal-hold'
                
                st.markdown(f"""
                <div class="metric-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3 style="color: #eaecef; margin: 0;">{result['ticker']}</h3>
                            <span class="value">{result['current_price']:.2f} ₺</span>
                            <span class="{chg_class}">{chg_icon} {chg:+.2f}%</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="{sig_class}">{signal}</span><br>
                            <small style="color: #848e9c;">RSI: {f"{result['rsi']:.1f}" if result.get('rsi') else 'N/A'}</small>
                        </div>
                    </div>
                    <div style="display: flex; gap: 2rem; margin-top: 0.5rem; color: #848e9c; font-size: 0.85rem;">
                        <span>Haftalık: <b class="{('change-up' if (result.get('change_1w') or 0) >= 0 else 'change-down')}">{(result.get('change_1w') or 0):+.2f}%</b></span>
                        <span>Aylık: <b class="{('change-up' if (result.get('change_1m') or 0) >= 0 else 'change-down')}">{(result.get('change_1m') or 0):+.2f}%</b></span>
                        <span>Hacim: {result.get('volume', 0):,.0f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.info("👆 Detaylı grafik ve teknik analiz için **📈 Hisse Analizi** sayfasına gidin")
            else:
                st.error(f"❌ {result['error']}")
    
    st.markdown("---")
    
    # ─── PİYASA ÖZETİ ───
    st.markdown("### 🌍 Piyasa Özeti")
    
    # Piyasa verilerini çek
    market_tickers = {
        'BIST 100': 'XU100.IS',
        'USD/TRY': 'USDTRY=X',
        'EUR/TRY': 'EURTRY=X',
        'Altın (gr)': 'GC=F',
    }
    
    cols = st.columns(len(market_tickers))
    for i, (name, ticker) in enumerate(market_tickers.items()):
        with cols[i]:
            try:
                r = analyze_stock(ticker, period="5d")
                if r['success']:
                    chg = r.get('change_1d', 0) or r.get('price_change_pct', 0)
                    icon = '▲' if chg >= 0 else '▼'
                    color = '#0ecb81' if chg >= 0 else '#f6465d'
                    price_fmt = f"{r['current_price']:,.2f}" if 'TRY' in ticker or 'GC' in ticker else f"{r['current_price']:,.0f}"
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>{name}</h4>
                        <div class="value">{price_fmt}</div>
                        <span style="color: {color}; font-weight: 600;">{icon} {chg:+.2f}%</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>{name}</h4>
                        <div class="value" style="color: #848e9c;">—</div>
                        <span style="color: #848e9c;">Yüklenemedi</span>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>{name}</h4>
                    <div class="value" style="color: #848e9c;">—</div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ─── POPÜLER HİSSELER ───
    st.markdown("### 🔥 Popüler BIST Hisseleri")
    
    popular = ['THYAO', 'ASELS', 'GARAN', 'AKBNK', 'TUPRS', 'EREGL', 'KCHOL', 'SISE']
    pop_cols = st.columns(4)
    
    for i, ticker in enumerate(popular):
        with pop_cols[i % 4]:
            try:
                r = analyze_stock(ticker, period="1mo")
                if r['success']:
                    chg = r.get('change_1d', 0) or 0
                    icon = '▲' if chg >= 0 else '▼'
                    color = '#0ecb81' if chg >= 0 else '#f6465d'
                    st.markdown(f"""
                    <div class="metric-card" style="padding: 0.8rem;">
                        <h4 style="margin: 0;">{ticker}</h4>
                        <span class="value" style="font-size: 1.2rem;">{r['current_price']:.2f}</span>
                        <span style="color: {color}; font-size: 0.85rem;">{icon}{chg:+.2f}%</span>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception:
                pass
    
    st.markdown("---")
    
    # ─── ENFLASYON ÖZETİ ───
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Enflasyon Özeti (TÜİK)")
        try:
            evds_df = load_evds_data_from_csv()
            if not evds_df.empty:
                latest = evds_df.iloc[-1]
                prev = evds_df.iloc[-2] if len(evds_df) > 1 else latest
                headline = latest.get('Genel TÜFE', 0)
                prev_headline = prev.get('Genel TÜFE', 0)
                delta_inf = headline - prev_headline
                
                inf_items = [
                    ('Manşet TÜFE', headline, delta_inf),
                    ('Gıda', latest.get('Gıda ve Alkolsüz İçecekler', 0), 0),
                    ('Çekirdek (B)', latest.get('B Endeksi (Çekirdek)', 0), 0),
                    ('Ulaştırma', latest.get('Ulaştırma', 0), 0),
                ]
                for name, val, delta in inf_items:
                    color = '#f6465d' if val > 50 else '#f0b90b' if val > 30 else '#0ecb81'
                    delta_str = f" ({delta:+.1f})" if delta else ""
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #2b3139;">
                        <span style="color: #848e9c;">{name}</span>
                        <span style="color: {color}; font-weight: 600;">%{val:.1f}{delta_str}</span>
                    </div>
                    """, unsafe_allow_html=True)
                st.caption("Kaynak: TÜİK resmi verileri")
            else:
                st.info("Enflasyon verileri henüz yüklenmemiş. Makro Analiz sayfasını ziyaret edin.")
        except Exception:
            st.info("Enflasyon verileri yüklenemedi.")
    
    with col2:
        st.markdown("### 📅 Yaklaşan Ekonomik Olaylar")
        try:
            upcoming = get_upcoming_high_importance_events(days=7)
            if upcoming is not None and not upcoming.empty:
                for _, event in upcoming.head(5).iterrows():
                    stars = '⭐' * event.get('Önem', 1)
                    flag = {'TRY': '🇹🇷', 'USD': '🇺🇸', 'EUR': '🇪🇺'}.get(event.get('Para Birimi', ''), '🌍')
                    date_str = pd.to_datetime(event['Tarih']).strftime('%d %b')
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #2b3139;">
                        <span>{flag} {event['Olay Adı']}</span>
                        <span style="color: #848e9c;">{date_str} {stars}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Yaklaşan yüksek önemli olay bulunamadı.")
        except Exception:
            st.info("Ekonomik takvim yüklenemedi.")


# ==================== HİSSE ANALİZİ ====================
def show_stock_analysis():
    """Profesyonel hisse analizi sayfası - Investing.com kalitesinde"""
    st.markdown("### 📈 Hisse Analizi")
    
    # ─── ARAMA ALANI ───
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ticker_input = st.text_input(
            "🔍 Hisse Ara", placeholder="THYAO, ASELS, AAPL...",
            key="stock_search", label_visibility="collapsed"
        )
    with col2:
        period = st.selectbox("Dönem", ["1mo", "3mo", "6mo", "1y", "2y"], index=2,
            format_func=lambda x: {"1mo": "1 Ay", "3mo": "3 Ay", "6mo": "6 Ay", "1y": "1 Yıl", "2y": "2 Yıl"}.get(x, x))
    with col3:
        analyze_btn = st.button("Analiz Et", type="primary", width='stretch')
    
    # Popüler hisseler
    pop_cols = st.columns(8)
    popular_tickers = ["THYAO", "GARAN", "ASELS", "KCHOL", "TUPRS", "FROTO", "BIMAS", "SISE"]
    selected_popular = None
    for i, t in enumerate(popular_tickers):
        with pop_cols[i]:
            if st.button(t, key=f"pop_{t}", width='stretch'):
                selected_popular = t
    
    if selected_popular:
        ticker_input = selected_popular
        analyze_btn = True
    
    if not (analyze_btn and ticker_input):
        st.info("⬆️ Hisse kodu yazıp **Analiz Et** butonuna basın veya yukarıdaki popüler hisselerden birini seçin.")
        return
    
    with st.spinner(f"📊 {ticker_input.upper()} analiz ediliyor..."):
        result = analyze_stock(ticker_input, period)
    
    if not result['success']:
        st.error(f"❌ {result['error']}")
        suggestions = search_stocks(ticker_input)
        if suggestions:
            st.markdown("**Bunu mu demek istediniz?**")
            for s in suggestions[:5]:
                st.markdown(f"- **{s['ticker']}** — {s['name']}")
        return
    
    # ─── FİYAT HEADER ───
    chg_1d = result.get('change_1d', 0) or 0
    chg_cls = 'price-up' if chg_1d >= 0 else 'price-down'
    chg_icon = '▲' if chg_1d >= 0 else '▼'
    signal = result['signals']['overall']
    sig_cls = 'signal-buy' if 'Al' in signal else 'signal-sell' if 'Sat' in signal else 'signal-hold'
    
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0;">
        <div>
            <span style="font-size: 1.5rem; font-weight: 700; color: #eaecef;">{result['ticker']}</span>
            <span style="font-size: 2rem; font-weight: 700; color: #eaecef; margin-left: 1rem;">{result['current_price']:.2f}</span>
            <span class="{chg_cls}" style="font-size: 1.1rem; margin-left: 0.5rem;">{chg_icon} {(result.get('price_change') or 0):.2f} ({chg_1d:+.2f}%)</span>
        </div>
        <div>
            <span class="{sig_cls}" style="font-size: 1rem;">{signal}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ─── DETAY METRİKLERİ ───
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Açılış", f"{(result.get('open') or 0):.2f}")
    col2.metric("Yüksek", f"{(result.get('high') or 0):.2f}")
    col3.metric("Düşük", f"{(result.get('low') or 0):.2f}")
    col4.metric("Haftalık", f"{(result.get('change_1w') or 0):+.2f}%")
    col5.metric("Aylık", f"{(result.get('change_1m') or 0):+.2f}%")
    col6.metric("Yıllık", f"{(result.get('yearly_return') or 0):+.2f}%")
    
    st.markdown("---")
    
    # ─── GRAFİKLER ───
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Fiyat", "📉 RSI & MACD", "🎯 Sinyaller", "📋 Detay"])
    
    df = result['data']
    
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df['Date'], open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name='Fiyat',
            increasing_line_color='#0ecb81', decreasing_line_color='#f6465d'
        ))
        if 'SMA_20' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA_20'], mode='lines',
                name='SMA 20', line=dict(color='#f0b90b', width=1)))
        if 'SMA_50' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA_50'], mode='lines',
                name='SMA 50', line=dict(color='#1a73e8', width=1)))
        if 'BB_High' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_High'], mode='lines',
                name='BB Üst', line=dict(color='#848e9c', width=1, dash='dot')))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Low'], mode='lines',
                name='BB Alt', line=dict(color='#848e9c', width=1, dash='dot'),
                fill='tonexty', fillcolor='rgba(132,142,156,0.05)'))
        
        # Destek/Direnç çizgileri
        sr = result.get('support_resistance', {})
        if sr.get('support'):
            fig.add_hline(y=sr['support'], line_dash="dash", line_color="#0ecb81",
                annotation_text=f"Destek: {sr['support']:.2f}")
        if sr.get('resistance'):
            fig.add_hline(y=sr['resistance'], line_dash="dash", line_color="#f6465d",
                annotation_text=f"Direnç: {sr['resistance']:.2f}")
        
        fig.update_layout(
            height=550, xaxis_rangeslider_visible=False,
            plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11',
            font_color='#eaecef',
            xaxis=dict(gridcolor='#1e2329', showgrid=True),
            yaxis=dict(gridcolor='#1e2329', showgrid=True, title="Fiyat (₺)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig)
    
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            fig_rsi = go.Figure()
            if 'RSI' in df.columns:
                fig_rsi.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], mode='lines',
                    line=dict(color='#a855f7', width=2), name='RSI'))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="#f6465d", annotation_text="Aşırı Alım (70)")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="#0ecb81", annotation_text="Aşırı Satım (30)")
            fig_rsi.add_hrect(y0=30, y1=70, fillcolor="#848e9c", opacity=0.05)
            fig_rsi.update_layout(title="RSI (14)", height=350, yaxis_range=[0, 100],
                plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11', font_color='#eaecef',
                xaxis=dict(gridcolor='#1e2329'), yaxis=dict(gridcolor='#1e2329'))
            st.plotly_chart(fig_rsi)
        
        with c2:
            fig_macd = go.Figure()
            if 'MACD' in df.columns:
                fig_macd.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], mode='lines',
                    line=dict(color='#1a73e8', width=2), name='MACD'))
            if 'MACD_Signal' in df.columns:
                fig_macd.add_trace(go.Scatter(x=df['Date'], y=df['MACD_Signal'], mode='lines',
                    line=dict(color='#f0b90b', width=1.5), name='Signal'))
            if 'MACD_Hist' in df.columns:
                colors = ['#0ecb81' if v > 0 else '#f6465d' for v in df['MACD_Hist'].fillna(0)]
                fig_macd.add_trace(go.Bar(x=df['Date'], y=df['MACD_Hist'], name='Histogram', marker_color=colors))
            fig_macd.update_layout(title="MACD", height=350,
                plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11', font_color='#eaecef',
                xaxis=dict(gridcolor='#1e2329'), yaxis=dict(gridcolor='#1e2329'))
            st.plotly_chart(fig_macd)
    
    with tab3:
        signals = result['signals']
        score = signals['score']
        
        # Gauge-style sinyal göstergesi
        if score >= 2:
            st.markdown(f'<div class="signal-buy" style="font-size: 1.3rem; text-align: center; padding: 1rem;">🟢 {signals["overall"]} — Güç: {signals["strength"]} (Puan: +{score})</div>', unsafe_allow_html=True)
        elif score <= -2:
            st.markdown(f'<div class="signal-sell" style="font-size: 1.3rem; text-align: center; padding: 1rem;">🔴 {signals["overall"]} — Güç: {signals["strength"]} (Puan: {score})</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="signal-hold" style="font-size: 1.3rem; text-align: center; padding: 1rem;">🟡 {signals["overall"]} — Güç: {signals["strength"]} (Puan: {score})</div>', unsafe_allow_html=True)
        
        st.markdown("")
        
        # Sinyal detayları tablo halinde
        buy_details = [d for d in signals['details'] if '🟢' in d]
        sell_details = [d for d in signals['details'] if '🔴' in d]
        neutral_details = [d for d in signals['details'] if '🟢' not in d and '🔴' not in d]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**🟢 AL Sinyalleri ({signals.get('buy_score', 0)})**")
            for d in buy_details:
                st.markdown(f"- {d}")
            if not buy_details:
                st.caption("Yok")
        with c2:
            st.markdown(f"**🔴 SAT Sinyalleri ({signals.get('sell_score', 0)})**")
            for d in sell_details:
                st.markdown(f"- {d}")
            if not sell_details:
                st.caption("Yok")
        with c3:
            st.markdown("**⚪ Nötr**")
            for d in neutral_details:
                st.markdown(f"- {d}")
            if not neutral_details:
                st.caption("Yok")
        
        st.markdown("---")
        sr = result.get('support_resistance', {})
        if sr:
            c1, c2, c3 = st.columns(3)
            c1.metric("🟢 Destek", f"{(sr.get('support') or 0):.2f}")
            c2.metric("🔴 Direnç", f"{(sr.get('resistance') or 0):.2f}")
            c3.metric("🔵 Pivot", f"{(sr.get('pivot') or 0):.2f}")
    
    with tab4:
        # Tüm teknik veriler tablosu
        detail_data = {
            'Gösterge': ['RSI (14)', 'MACD', 'MACD Signal', 'MACD Histogram',
                         'SMA 20', 'SMA 50', 'Bollinger Üst', 'Bollinger Alt',
                         'Stochastic %K', 'Stochastic %D', 'ATR',
                         '52H Yüksek', '52H Düşük', 'Ort. Hacim (20g)'],
            'Değer': [
                f"{result['rsi']:.2f}" if result.get('rsi') else "N/A",
                f"{result['macd']:.4f}" if result.get('macd') else "N/A",
                f"{result['macd_signal']:.4f}" if result.get('macd_signal') else "N/A",
                f"{result['macd_hist']:.4f}" if result.get('macd_hist') else "N/A",
                f"{result['sma_20']:.2f}" if result.get('sma_20') else "N/A",
                f"{result['sma_50']:.2f}" if result.get('sma_50') else "N/A",
                f"{result['bb_high']:.2f}" if result.get('bb_high') else "N/A",
                f"{result['bb_low']:.2f}" if result.get('bb_low') else "N/A",
                f"{result['stoch_k']:.2f}" if result.get('stoch_k') else "N/A",
                f"{result['stoch_d']:.2f}" if result.get('stoch_d') else "N/A",
                f"{result['atr']:.2f}" if result.get('atr') else "N/A",
                f"{(result.get('high_52w') or 0):.2f}",
                f"{(result.get('low_52w') or 0):.2f}",
                f"{(result.get('avg_volume') or 0):,.0f}",
            ]
        }
        st.dataframe(pd.DataFrame(detail_data), width='stretch', hide_index=True)


# ==================== KİŞİSEL KARŞILAŞTIRMA ====================
def show_personal_comparison():
    """Kişisel enflasyon vs hisse karşılaştırması"""
    st.markdown("### 💰 Enflasyon vs Hisse Getirisi")
    st.caption("Seçtiğin hissenin senin market sepetindeki enflasyonu yenip yenmediğini analiz et.")
    
    # Kişisel enflasyon özeti
    with st.expander("📊 Senin Market Enflasyonun (Detay)", expanded=False):
        inflation = calculate_personal_inflation(days=30)
        
        if inflation['success']:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("30 Günlük Enflasyon", f"%{inflation['inflation']:.2f}")
            with col2:
                st.metric("Ağırlıklı", f"%{inflation['weighted_inflation']:.2f}")
            with col3:
                st.metric("Takip Edilen Ürün", inflation['product_count'])
            
            if inflation['top_increases']:
                st.markdown("**En çok artan ürünler:**")
                for p in inflation['top_increases'][:3]:
                    st.markdown(f"- {p['product_name']}: %{p['change_pct']:.1f}")
        else:
            st.warning("⚠️ Market verisi yok. Önce market botunu çalıştırın veya örnek veri yükleyin.")
            if st.button("📦 Örnek Veri Yükle"):
                from market_bot import generate_sample_prices
                generate_sample_prices()
                st.rerun()
    
    st.divider()
    
    # Hisse karşılaştırma
    col1, col2 = st.columns([2, 1])
    
    with col1:
        compare_ticker = st.text_input(
            "🔍 Karşılaştırmak istediğin hisse",
            placeholder="THYAO, ASELS, KCHOL...",
            key="compare_ticker"
        )
    
    with col2:
        compare_days = st.selectbox(
            "📅 Karşılaştırma Dönemi",
            [7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"{x} gün"
        )
    
    compare_btn = st.button("⚡ Karşılaştır", type="primary")
    
    if compare_btn and compare_ticker:
        with st.spinner("Analiz yapılıyor..."):
            result = compare_inflation_vs_stock(compare_ticker, days=compare_days)
        
        if not result['success']:
            st.error(f"❌ {result['error']}")
            return
        
        # Sonuç kartı
        st.markdown("---")
        
        # Ana sonuç
        if result['real_return'] > 0:
            st.markdown(f"""
            <div class="verdict-win">
                <h2>{result['emoji']} {result['verdict']}</h2>
                <p style="font-size: 1.2rem;">{result['comment']}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="verdict-lose">
                <h2>{result['emoji']} {result['verdict']}</h2>
                <p style="font-size: 1.2rem;">{result['comment']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Detaylı metrikler
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🛒 Senin Enflasyonun",
                f"%{result['personal_inflation']:.2f}",
                f"~%{result['projected_yearly_inflation']:.0f}/yıl"
            )
        
        with col2:
            st.metric(
                f"📈 {result['ticker']} Getirisi",
                f"%{result['stock_return']:.2f}",
                f"~%{result['projected_yearly_return']:.0f}/yıl"
            )
        
        with col3:
            delta_color = "normal" if result['real_return'] > 0 else "inverse"
            st.metric(
                "💎 Reel Getiri",
                f"%{result['real_return']:.2f}",
                "Enflasyonu yendi" if result['real_return'] > 0 else "Enflasyona yenildi",
                delta_color=delta_color
            )
        
        with col4:
            st.metric("🎯 Sinyal", result['signal'])
        
        # Öneri
        st.markdown("### 💡 Öneri")
        recommendation = generate_recommendation(result)
        st.info(recommendation)
    
    st.divider()
    
    # Çoklu karşılaştırma
    st.markdown("### 📊 Birden Fazla Hisse Karşılaştır")
    
    multi_tickers = st.text_input(
        "Hisse kodlarını virgülle ayırarak yazın",
        placeholder="THYAO, GARAN, ASELS, KCHOL, FROTO",
        key="multi_compare"
    )
    
    if st.button("📊 Hepsini Karşılaştır"):
        tickers = [t.strip() for t in multi_tickers.split(",") if t.strip()]
        
        if tickers:
            with st.spinner("Karşılaştırma yapılıyor..."):
                comparison_df = multi_stock_comparison(tickers, days=compare_days)
            
            if not comparison_df.empty:
                st.dataframe(
                    comparison_df,
                    width='stretch',
                    hide_index=True
                )
                
                # Grafik
                fig = px.bar(
                    comparison_df,
                    x='Hisse',
                    y='Reel Getiri %',
                    color='Reel Getiri %',
                    color_continuous_scale=['#f6465d', '#f0b90b', '#0ecb81'],
                    title='Enflasyona Göre Reel Getiri'
                )
                fig.add_hline(y=0, line_dash="dash", line_color="#848e9c")
                fig.update_layout(plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11', font_color='#eaecef')
    st.markdown("### 🏆 Enflasyonu Yenen BIST Hisseleri")
    
    if st.button("🔍 Otomatik Tara"):
        with st.spinner("BIST hisseleri taranıyor... (Bu biraz sürebilir)"):
            beaters = find_inflation_beaters(min_return=0, days=30)
        
        if beaters:
            df = pd.DataFrame(beaters)
            df.columns = ['Hisse', 'Getiri %', 'Reel Getiri %', 'Sinyal', 'Fiyat']
            
            st.dataframe(df, width='stretch', hide_index=True)
            st.success(f"✅ {len(beaters)} hisse enflasyonu yendi!")
        else:
            st.warning("Enflasyonu yenen hisse bulunamadı.")


# ==================== MARKET ENFLASYONU ====================
def show_market_inflation():
    """Market enflasyonu detay sayfası"""
    st.markdown("### 🛒 Market Enflasyonu Analizi")
    
    # Filtreler
    col1, col2 = st.columns(2)
    with col1:
        days = st.slider("Analiz Süresi (Gün)", 7, 90, 30)
    with col2:
        market = st.selectbox("Market", ["Tümü", "Migros"])
    
    market_name = None if market == "Tümü" else market

    # Fiyatların güncelliğini enflasyon sonuçlarından bağımsız göster.
    connection = get_connection()
    try:
        freshness = get_market_data_freshness(connection, market_name=market_name)
    finally:
        connection.close()

    if freshness['status'] == 'fresh':
        st.caption(f"Son market fiyat kaydı: {freshness['latest_date']} ({freshness['age_days']} gün önce)")
    elif freshness['status'] == 'stale':
        st.warning(f"⚠️ Market fiyatları güncel değil: son kayıt {freshness['latest_date']} ({freshness['age_days']} gün önce).")
    elif freshness['status'] == 'future':
        st.warning(f"⚠️ Son market fiyat kaydı gelecekte: {freshness['latest_date']}. Tarihi kontrol edin.")
    elif freshness['status'] == 'invalid':
        st.warning("⚠️ Son market fiyat kaydının tarihi geçersiz.")
    else:
        st.info("Seçilen market için henüz fiyat kaydı bulunmuyor.")

    # Enflasyon hesapla
    inflation = calculate_personal_inflation(days=days, market_name=market_name)
    
    if not inflation['success']:
        st.warning(inflation.get('error', 'Veri bulunamadı'))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📦 Örnek Veri Yükle", type="primary"):
                from market_bot import generate_sample_prices
                generate_sample_prices()
                st.rerun()
        with col2:
            if st.button("🔄 Market Botunu Çalıştır"):
                st.info("Terminal'de şu komutu çalıştırın: `python market_bot.py --now`")
        return
    
    # Metrikler
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Sepet Enflasyonu", f"%{inflation['inflation']:.2f}")
    with col2:
        st.metric("Ağırlıklı", f"%{inflation['weighted_inflation']:.2f}")
    with col3:
        yearly_proj = (inflation['inflation'] / days) * 365
        st.metric("Yıllık Projeksiyon", f"~%{yearly_proj:.0f}")
    with col4:
        st.metric("Ürün Sayısı", inflation['product_count'])
    
    st.divider()
    
    # Ürün tablosu
    if inflation['all_products']:
        df = pd.DataFrame(inflation['all_products'])
        df.columns = ['Ürün', 'İlk Fiyat', 'Son Fiyat', 'Değişim %']
        
        st.dataframe(
            df,
            width='stretch',
            hide_index=True
        )
        
        # Grafik
        fig = px.bar(
            df.sort_values('Değişim %', ascending=True),
            x='Değişim %',
            y='Ürün',
            orientation='h',
            color='Değişim %',
            color_continuous_scale=['#0ecb81', '#f0b90b', '#f6465d']
        )
        fig.update_layout(height=max(400, len(df) * 25),
            plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11', font_color='#eaecef')
        st.plotly_chart(fig)


# ==================== MAKRO ANALİZ ====================
def show_macro_analysis():
    """TCMB rapor stilinde makro ekonomik analiz sayfası"""
    st.markdown("### 🏦 Makro Ekonomik Analiz")
    st.caption("TCMB EVDS verilerine dayalı profesyonel enflasyon analizi")
    
    # Veri kaynağı seçimi - Varsayılan: EVDS API (gerçek veri)
    with st.sidebar:
        st.markdown("### ⚙️ Veri Ayarları")
        
        data_source = st.radio(
            "Veri Kaynağı",
            ["EVDS API", "Simüle Veri"],
            index=0,
            help="EVDS API ile TCMB'den gerçek enflasyon verisi çekilir"
        )
        
        if data_source == "EVDS API":
            api_key = st.text_input(
                "EVDS API Anahtarı",
                value=os.environ.get("EVDS_API_KEY", ""),
                type="password",
                help="evds.tcmb.gov.tr adresinden ücretsiz alabilirsiniz"
            )
        else:
            api_key = None
        
        start_year = st.selectbox(
            "Başlangıç Yılı",
            [2003, 2010, 2015, 2020, 2021, 2022, 2023, 2024, 2025],
            index=3
        )
    
    # Veriyi çek
    use_simulation = (data_source == "Simüle Veri")
    start_date = f"01-01-{start_year}"
    
    with st.spinner("Enflasyon verileri yükleniyor..."):
        if not use_simulation and api_key:
            # EVDS API: Gerçek veriyi çekmeyi dene (fallback zinciri ile)
            evds_df, metrics = get_evds_inflation_data(
                api_key=api_key,
                use_simulation=False,
                start_date=start_date
            )
            if not evds_df.empty:
                save_evds_data_to_csv(evds_df)
        else:
            # Simülasyon modu
            evds_df, metrics = get_evds_inflation_data(
                api_key=None,
                use_simulation=True,
                start_date=start_date
            )
    
    # Veri kaynağı bilgisi göster
    source = metrics.get('data_source', 'bilinmeyen')
    source_labels = {
        'evds_rest': '✅ TCMB EVDS API (Canlı)',
        'evds_lib': '✅ TCMB EVDS Kütüphanesi (Canlı)',
        'csv_cache': '📂 Kayıtlı Veri (CSV)',
        'referans': '📊 Referans Veri',
    }
    st.info(f"📡 Veri Kaynağı: {source_labels.get(source, source)}")
    
    if source in ('csv_cache', 'referans'):
        st.warning("⚠️ EVDS API'ye bağlanılamadı. Önbellek/referans verisi gösteriliyor. API anahtarınızı kontrol edin.")
    
    if evds_df.empty:
        st.error("Veri yüklenemedi! Lütfen veri kaynağını kontrol edin.")
        return
    
    # Kişisel enflasyon verisi
    personal_df = None
    personal_inflation = calculate_personal_inflation(days=365)
    
    if personal_inflation['success']:
        # Kişisel veriden ölçeklenmiş zaman serisi oluştur
        personal_rate = personal_inflation['inflation']
        official_last = evds_df['Genel TÜFE'].iloc[-1] if not evds_df.empty else 50
        scale_factor = personal_rate / official_last if official_last != 0 else 1.0
        personal_df = pd.DataFrame({
            'Tarih': evds_df['Tarih'],
            'Kisisel_Enflasyon': evds_df['Genel TÜFE'] * scale_factor
        })
    
    # Özet Metrikler
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "📊 Manşet Enflasyon",
            f"%{metrics.get('latest_headline', 0):.1f}",
            help="TÜİK TÜFE Yıllık Değişim"
        )
    
    with col2:
        st.metric(
            "🎯 Çekirdek (B)",
            f"%{metrics.get('latest_core', 0):.1f}",
            help="İşlenmemiş gıda ve enerji hariç"
        )
    
    with col3:
        st.metric(
            "🍞 Gıda",
            f"%{metrics.get('food_inflation', 0):.1f}",
            help="Gıda ve Alkolsüz İçecekler"
        )
    
    with col4:
        st.metric(
            "🏠 Konut",
            f"%{metrics.get('housing_inflation', 0):.1f}",
            help="Kira, Elektrik, Su, Gaz"
        )
    
    with col5:
        st.metric(
            "🚗 Ulaştırma",
            f"%{metrics.get('transport_inflation', 0):.1f}",
            help="Akaryakıt ve Taşımacılık"
        )
    
    st.markdown("---")
    
    # Görselleştirmeler
    viz = MacroVisualizer()
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Trend Grafiği",
        "🌡️ Isı Haritası", 
        "📊 Makas Grafiği",
        "📋 Kategori Kırılımı"
    ])
    
    with tab1:
        st.markdown("### Resmi vs Kişisel Enflasyon Trendi")
        fig = viz.create_trend_chart(evds_df, personal_df)
        st.plotly_chart(fig)
        
        st.info("""
        **📝 Okuma Rehberi:**
        - 🔴 Kırmızı çizgi: Resmi TÜFE (TÜİK)
        - 🔵 Mavi çizgi: Kişisel enflasyonunuz
        - 🟢 Yeşil kesikli: Çekirdek enflasyon (volatilite hariç)
        """)
    
    with tab2:
        st.markdown("### Aylık Enflasyon Yoğunluğu")
        fig = viz.create_heatmap(evds_df)
        st.plotly_chart(fig)
        
        st.info("""
        **📝 Okuma Rehberi:**
        - Koyu kırmızı: Yüksek enflasyon dönemleri
        - Yeşil: Düşük enflasyon dönemleri
        - Genellikle Ocak ve Temmuz ayları zamlardan dolayı yüksek çıkar
        """)
    
    with tab3:
        st.markdown("### Kişisel - Resmi Enflasyon Farkı")
        
        if personal_df is not None:
            fig = viz.create_spread_chart(evds_df, personal_df)
            st.plotly_chart(fig)
            
            st.info("""
            **📝 Okuma Rehberi:**
            - 🔴 Pozitif çubuklar: Kişisel enflasyonunuz resmi veriden yüksek
            - 🟢 Negatif çubuklar: Kişisel enflasyonunuz resmi veriden düşük
            - Büyük farklar harcama alışkanlıklarınızın ortalamadan farklı olduğunu gösterir
            """)
        else:
            st.warning("Makas grafiği için kişisel enflasyon verisi gerekli. Market botunu çalıştırın.")
    
    with tab4:
        st.markdown("### Alt Kategori Enflasyonları")
        fig = viz.create_category_breakdown(evds_df, latest_only=True)
        st.plotly_chart(fig)
        
        # TÜİK Ağırlıkları tablosu
        st.markdown("#### 📊 TÜİK 2025 Sepet Ağırlıkları")
        weights_df = pd.DataFrame([
            {'Kategori': k, 'Ağırlık %': v['weight']} 
            for k, v in TUIK_WEIGHTS_2025.items()
        ]).sort_values('Ağırlık %', ascending=False)
        
        st.dataframe(weights_df, width='stretch', hide_index=True)
    
    # Veri güncelleme butonu
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Verileri Yenile", width='stretch'):
            evds_df, metrics = get_evds_inflation_data(
                api_key=api_key,
                use_simulation=use_simulation,
                start_date=start_date
            )
            save_evds_data_to_csv(evds_df)
            st.success("✅ Veriler güncellendi!")
            st.rerun()
    
    with col2:
        if st.button("📥 CSV İndir", width='stretch'):
            csv = evds_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="💾 evds_inflation.csv",
                data=csv,
                file_name="evds_inflation.csv",
                mime="text/csv"
            )


# ==================== EKONOMİK TAKVİM ====================
def show_economic_calendar():
    """Ekonomik takvim sayfası - Deterministik takvim + TCMB RSS"""
    st.markdown("### 📅 Ekonomik Takvim")
    st.caption("Kaynak: TÜİK, TCMB, Fed, ECB resmi yayın takvimleri")
    
    # Filtreler
    col1, col2, col3 = st.columns(3)
    
    with col1:
        countries = st.multiselect(
            "🌍 Ülkeler",
            options=['TR', 'US', 'EU'],
            default=['TR', 'US'],
            format_func=lambda x: {
                'TR': '🇹🇷 Türkiye',
                'US': '🇺🇸 ABD',
                'EU': '🇪🇺 Euro Bölgesi'
            }.get(x, x)
        )
    
    with col2:
        importance = st.selectbox(
            "⭐ Önem Seviyesi",
            options=['all', 'high', 'medium'],
            format_func=lambda x: {
                'all': '📊 Tümü',
                'high': '⭐⭐⭐ Yüksek (Fed, TCMB)',
                'medium': '⭐⭐ Orta ve Üstü'
            }.get(x, x)
        )
    
    with col3:
        days = st.slider("📆 Gün Sayısı", min_value=1, max_value=60, value=14)
    
    with st.spinner("📅 Ekonomik takvim oluşturuluyor..."):
        df = get_economic_calendar(
            countries=countries,
            importance=importance,
            days=days
        )
    
    if df.empty:
        st.warning("Seçilen kriterlere uygun olay bulunamadı.")
        return
    
    # Bugünkü olayları işaretle
    df = highlight_today_events(df)
    
    # Özet metrikler
    st.markdown("---")
    today = datetime.now().date()
    today_events = df[pd.to_datetime(df['Tarih']).dt.date == today]
    high_importance = df[df['Önem'] >= 3]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Toplam Olay", len(df))
    
    with col2:
        st.metric("📌 Bugün", len(today_events))
    
    with col3:
        st.metric("⭐ Yüksek Önem", len(high_importance))
    
    with col4:
        tr_events = len(df[df['Para Birimi'] == 'TRY'])
        st.metric("🇹🇷 Türkiye", tr_events)
    
    st.markdown("---")
    
    # Bugünkü önemli olaylar vurgusu
    if not today_events.empty:
        st.markdown("### 📌 Bugünkü Olaylar")
        
        for _, event in today_events.iterrows():
            importance_stars = '⭐' * event['Önem']
            currency_flag = {'TRY': '🇹🇷', 'USD': '🇺🇸', 'EUR': '🇪🇺'}.get(event['Para Birimi'], '🌍')
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{event['Saat']}** {currency_flag} {event['Olay Adı']} {importance_stars}")
            with col2:
                if event['Açıklanan'] != '-':
                    st.markdown(f"Açıklanan: **{event['Açıklanan']}**")
        
        st.markdown("---")
    
    # Ana tablo
    st.markdown("### 📋 Bu Haftanın Ekonomik Verileri")
    
    # Görsel formatla
    display_df = df.copy()
    display_df['Önem'] = display_df['Önem'].apply(lambda x: '⭐' * x)
    display_df['Para Birimi'] = display_df['Para Birimi'].apply(
        lambda x: f"{'🇹🇷' if x=='TRY' else '🇺🇸' if x=='USD' else '🇪🇺' if x=='EUR' else '🌍'} {x}"
    )
    display_df['Tarih'] = pd.to_datetime(display_df['Tarih']).dt.strftime('%d %b %Y')
    
    # Sütun sırası
    column_order = ['Bugün', 'Tarih', 'Saat', 'Para Birimi', 'Olay Adı', 'Önem', 'Beklenti', 'Açıklanan', 'Önceki']
    display_df = display_df[[col for col in column_order if col in display_df.columns]]
    
    # Tabloyu göster
    st.dataframe(
        display_df,
        width='stretch',
        height=400
    )
    
    # Önemli olaylar açıklaması
    with st.expander("📖 Önemli Veriler Rehberi", expanded=False):
        st.markdown("""
        ### 🇹🇷 Türkiye Verileri
        
        | Veri | Açıklama | Etki |
        |------|----------|------|
        | **TCMB Faiz Kararı** | Politika faizi kararı | TL ve borsa üzerinde yüksek etki |
        | **TÜFE (Enflasyon)** | Aylık tüketici fiyat endeksi | Faiz beklentilerini etkiler |
        | **İşsizlik Oranı** | Aylık işsizlik verisi | Ekonomik aktivite göstergesi |
        
        ### 🇺🇸 ABD Verileri
        
        | Veri | Açıklama | Etki |
        |------|----------|------|
        | **Fed Faiz Kararı** | Federal Reserve faiz kararı | Küresel piyasalarda yüksek etki |
        | **Tarım Dışı İstihdam** | Aylık istihdam değişimi | Dolar ve küresel piyasalar |
        | **CPI (Enflasyon)** | Tüketici fiyat endeksi | Fed politika beklentileri |
        
        **⚠️ Önemli:** Yüksek önemli veriler açıklandığında volatilite artabilir.
        """)
    
    st.markdown("---")
    st.caption("📝 Veriler bilgilendirme amaçlıdır. Saatler Türkiye saatine göredir.")


# ==================== VERİ YÖNETİMİ ====================
def show_data_management():
    """Veri yönetimi ve güncelleme"""
    st.markdown("### 🔄 Veri Yönetimi")
    
    tab1, tab2, tab3 = st.tabs(["📦 Veri Güncelle", "📋 Ürün Listesi", "📊 Veritabanı"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🛒 Market Verileri")
            
            if st.button("📦 Örnek Veri Yükle", type="primary", width='stretch'):
                with st.spinner("Örnek veriler üretiliyor..."):
                    from market_bot import generate_sample_prices
                    generate_sample_prices()
                st.success("✅ 30 günlük örnek veri yüklendi!")
            
            st.markdown("---")
            
            st.markdown("#### 🤖 Otomatik Bot")
            st.code("python market_bot.py --now", language="bash")
            st.caption("Terminal'de çalıştırarak gerçek fiyatları çekebilirsiniz.")
            
            st.code("python market_bot.py --schedule", language="bash")
            st.caption("Her sabah 09:00'da otomatik çalışır.")
        
        with col2:
            st.markdown("### 📈 Borsa Verileri")
            
            if st.button("🔄 Örnek Hisseleri Güncelle", type="primary", width='stretch'):
                with st.spinner("Hisse verileri çekiliyor..."):
                    from scrapers.macro_data import fetch_all_stocks, fetch_macro_data
                    fetch_all_stocks()
                    fetch_macro_data()
                st.success("✅ Hisse verileri güncellendi!")
            
            st.info("💡 Hisse verileri anlık olarak yfinance'den çekilir. Güncellemeye gerek yok.")
    
    with tab2:
        st.markdown("### 📋 Takip Edilen Ürünler")
        st.markdown("Ürün listesini düzenlemek için `urunler.csv` dosyasını açın.")
        
        csv_path = os.path.join(os.path.dirname(__file__), 'urunler.csv')
        
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            st.dataframe(df, width='stretch', hide_index=True)
            
            st.download_button(
                "📥 CSV İndir",
                df.to_csv(index=False).encode('utf-8'),
                "urunler.csv",
                "text/csv"
            )
        else:
            st.warning("CSV dosyası bulunamadı.")
    
    with tab3:
        st.markdown("### 💾 Veritabanı Durumu")
        
        conn = get_connection()
        
        stats = {}
        for table in ['products', 'stocks', 'macro_data', 'signals']:
            try:
                count = pd.read_sql_query(f"SELECT COUNT(*) as cnt FROM {table}", conn)['cnt'].iloc[0]
                stats[table] = count
            except Exception:
                stats[table] = 0
        
        conn.close()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🛒 Ürün Kayıtları", stats['products'])
        col2.metric("📈 Hisse Kayıtları", stats['stocks'])
        col3.metric("📊 Makro Veriler", stats['macro_data'])
        col4.metric("🎯 Sinyaller", stats['signals'])


# ==================== ENFLASYON HESAPLAMA MOTORU ====================
def show_inflation_calculator():
    """TÜİK ve İTO metodolojisi ile enflasyon hesaplama sayfası"""
    st.markdown("### 🧮 Enflasyon Hesaplama Motoru")
    
    st.markdown("""
    **TÜİK ve İTO metodolojisini simule eden gelişmiş enflasyon hesaplayıcı.**
    
    Bu motor, market sepetinizdeki ürünleri TÜİK ve İTO'nun resmi harcama grubu 
    ağırlıklarına göre sınıflandırır ve 3 farklı yöntemle kişisel enflasyonunuzu hesaplar.
    """)
    
    st.divider()
    
    # Hesaplama parametreleri
    col1, col2 = st.columns(2)
    with col1:
        calc_days = st.slider("📅 Hesaplama Dönemi (Gün)", 7, 90, 30)
    with col2:
        show_details = st.checkbox("📋 Detaylı Görüntüle", value=True)
    
    calculate_btn = st.button("🚀 Hesapla", type="primary", width='stretch')
    
    if calculate_btn:
        with st.spinner("Enflasyon hesaplanıyor..."):
            calculator = InflationCalculator()
            result = calculator.calculate(days=calc_days)
        
        if not result.success:
            st.error(f"❌ {result.error}")
            if st.button("📦 Örnek Veri Yükle"):
                from market_bot import generate_sample_prices
                generate_sample_prices()
                st.rerun()
            return
        
        # Ana sonuçlar
        st.success(f"✅ Hesaplama tamamlandı! ({result.total_products} ürün, {result.period_days} gün)")
        
        st.markdown("### 📊 3 Farklı Yöntemle Enflasyon")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1e3c72, #2a5298); 
                        padding: 1.5rem; border-radius: 10px; text-align: center; color: white;">
                <h4>🇹🇷 TÜİK Metodolojisi</h4>
                <h2 style="font-size: 2.5rem; margin: 0.5rem 0;">%{:.2f}</h2>
                <p style="opacity: 0.8;">Tüketici Fiyat Endeksi ağırlıkları</p>
            </div>
            """.format(result.tuik_inflation), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #11998e, #38ef7d); 
                        padding: 1.5rem; border-radius: 10px; text-align: center; color: white;">
                <h4>🏢 İTO Metodolojisi</h4>
                <h2 style="font-size: 2.5rem; margin: 0.5rem 0;">%{:.2f}</h2>
                <p style="opacity: 0.8;">Ücretliler Geçinme Endeksi ağırlıkları</p>
            </div>
            """.format(result.ito_inflation), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #f093fb, #f5576c); 
                        padding: 1.5rem; border-radius: 10px; text-align: center; color: white;">
                <h4>⚖️ Ham (Eşit Ağırlıklı)</h4>
                <h2 style="font-size: 2.5rem; margin: 0.5rem 0;">%{:.2f}</h2>
                <p style="opacity: 0.8;">Basit aritmetik ortalama</p>
            </div>
            """.format(result.raw_inflation), unsafe_allow_html=True)
        
        # Yıllık projeksiyon
        st.markdown("### 📈 Yıllık Projeksiyon")
        yearly_tuik = (result.tuik_inflation / calc_days) * 365
        yearly_ito = (result.ito_inflation / calc_days) * 365
        yearly_raw = (result.raw_inflation / calc_days) * 365
        
        col1, col2, col3 = st.columns(3)
        col1.metric("TÜİK Yıllık", f"~%{yearly_tuik:.0f}")
        col2.metric("İTO Yıllık", f"~%{yearly_ito:.0f}")
        col3.metric("Ham Yıllık", f"~%{yearly_raw:.0f}")
        
        st.divider()
        
        if show_details:
            # Kategori bazlı analiz
            st.markdown("### 📁 Kategori Bazlı Analiz")
            
            tab1, tab2, tab3 = st.tabs(["📊 Kategori Değişimleri", "⚖️ Ağırlık Karşılaştırması", "📝 TÜİK/İTO Ağırlıkları"])
            
            with tab1:
                if result.category_breakdown:
                    # DataFrame oluştur
                    cat_data = []
                    for cat, data in result.category_breakdown.items():
                        tuik_w = result.tuik_weights_used.get(cat, 0)
                        ito_w = result.ito_weights_used.get(cat, 0)
                        cat_data.append({
                            'Kategori': cat,
                            'Ürün Sayısı': data.product_count,
                            'Ortalama Değişim %': data.avg_change_pct,
                            'Min %': data.min_change_pct,
                            'Max %': data.max_change_pct,
                            'TÜİK Ağırlık %': tuik_w,
                            'İTO Ağırlık %': ito_w
                        })
                    
                    df_cat = pd.DataFrame(cat_data)
                    df_cat = df_cat.sort_values('Ortalama Değişim %', ascending=False)
                    
                    st.dataframe(df_cat, width='stretch', hide_index=True)
                    
                    # Grafik
                    fig = px.bar(
                        df_cat,
                        x='Kategori',
                        y='Ortalama Değişim %',
                        color='Ortalama Değişim %',
                        color_continuous_scale=['#0ecb81', '#f0b90b', '#f6465d'],
                        title='Kategori Bazlı Fiyat Değişimleri'
                    )
                    fig.update_layout(xaxis_tickangle=-45,
                        plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11', font_color='#eaecef')
                    st.plotly_chart(fig)
            
            with tab2:
                # TÜİK vs İTO ağırlık karşılaştırması
                if result.tuik_weights_used and result.ito_weights_used:
                    weight_data = []
                    for cat in result.tuik_weights_used.keys():
                        weight_data.append({
                            'Kategori': cat,
                            'TÜİK Ağırlık': result.tuik_weights_used.get(cat, 0),
                            'İTO Ağırlık': result.ito_weights_used.get(cat, 0)
                        })
                    
                    df_weights = pd.DataFrame(weight_data)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        name='TÜİK',
                        x=df_weights['Kategori'],
                        y=df_weights['TÜİK Ağırlık'],
                        marker_color='#1a73e8'
                    ))
                    fig.add_trace(go.Bar(
                        name='İTO',
                        x=df_weights['Kategori'],
                        y=df_weights['İTO Ağırlık'],
                        marker_color='#0ecb81'
                    ))
                    fig.update_layout(
                        barmode='group',
                        title='TÜİK vs İTO Ağırlık Karşılaştırması',
                        xaxis_tickangle=-45,
                        plot_bgcolor='#0b0e11', paper_bgcolor='#0b0e11', font_color='#eaecef'
                    )
                    st.plotly_chart(fig)
            
            with tab3:
                # Resmi ağırlıklar tablosu
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 🇹🇷 TÜİK TÜFE Ağırlıkları")
                    tuik_df = pd.DataFrame([
                        {'Kategori': k, 'Ağırlık %': v} 
                        for k, v in sorted(TUIK_WEIGHTS.items(), key=lambda x: x[1], reverse=True)
                    ])
                    st.dataframe(tuik_df, width='stretch', hide_index=True)
                
                with col2:
                    st.markdown("#### 🏢 İTO Geçinme Endeksi Ağırlıkları")
                    ito_df = pd.DataFrame([
                        {'Kategori': k, 'Ağırlık %': v} 
                        for k, v in sorted(ITO_WEIGHTS.items(), key=lambda x: x[1], reverse=True)
                    ])
                    st.dataframe(ito_df, width='stretch', hide_index=True)
        
        # Formül açıklaması
        st.divider()
        with st.expander("📖 Hesaplama Formülü", expanded=False):
            st.markdown("""
            ### Ağırlıklı Enflasyon Formülü
            
            ```
            Enflasyon = Σ(Kategori_Değişimi × Kategori_Ağırlığı) / 100
            ```
            
            **Örnek:**
            - Gıda değişimi: %10, Ağırlık: %25 → Katkı: 10 × 0.25 = 2.5
            - Ulaştırma değişimi: %5, Ağırlık: %15 → Katkı: 5 × 0.15 = 0.75
            - ...
            - **Toplam Enflasyon** = Tüm katkıların toplamı
            
            ### Yöntem Farkları
            
            | Yöntem | Açıklama |
            |--------|----------|
            | **TÜİK** | Resmi tüketici fiyat endeksi ağırlıkları (TÜFE) |
            | **İTO** | İstanbul Ticaret Odası ücretliler geçinme endeksi |
            | **Ham** | Tüm kategorilere eşit ağırlık (basit ortalama) |
            """)


# ==================== MAIN ====================
def main():
    """Ana uygulama"""
    init_data()
    
    # Sidebar
    st.sidebar.title("💰 FinApp v4.0")
    st.sidebar.markdown("---")
    
    # Sayfa seçimi
    page = st.sidebar.radio(
        "📍 Sayfa Seçin",
        [
            "🏠 Ana Sayfa",
            "📈 Hisse Analizi",
            "🤖 AI Analiz",
            "📰 Haberler",
            "💰 Enflasyon vs Hisse",
            "🏦 Makro Analiz",
            "📅 Ekonomik Takvim",
            "🧮 Enflasyon Hesaplayıcı",
            "🛒 Market Enflasyonu",
            "🔄 Veri Yönetimi"
        ]
    )
    
    # Sayfa yönlendirme
    if page == "🏠 Ana Sayfa":
        show_home_page()
    elif page == "📈 Hisse Analizi":
        show_stock_analysis()
    elif page == "🤖 AI Analiz":
        render_ai_analysis_tab()
    elif page == "📰 Haberler":
        render_news_tab()
    elif page == "💰 Enflasyon vs Hisse":
        show_personal_comparison()
    elif page == "🏦 Makro Analiz":
        show_macro_analysis()
    elif page == "📅 Ekonomik Takvim":
        show_economic_calendar()
    elif page == "🧮 Enflasyon Hesaplayıcı":
        show_inflation_calculator()
    elif page == "🛒 Market Enflasyonu":
        show_market_inflation()
    elif page == "🔄 Veri Yönetimi":
        show_data_management()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **FinApp v4.0**
    
    📊 Profesyonel Finansal Analiz
    🤖 AI Destekli Tahminler
    📰 Gerçek Zamanlı Veri
    
    ⚠️ *Yatırım tavsiyesi değildir.*
    """)


if __name__ == '__main__':
    main()
