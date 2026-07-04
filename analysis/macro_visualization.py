"""
Makro Analiz Görselleştirme Modülü (macro_visualization.py)
==========================================================
TCMB rapor stilinde profesyonel grafikler üretir.

Grafikler:
1. Trend Grafiği: Resmi vs Kişisel Enflasyon karşılaştırması
2. Isı Haritası (Heatmap): Aylık enflasyon yoğunluğu
3. Spread (Makas) Grafiği: Kişisel-Resmi fark analizi

Kullanım:
    from analysis.macro_visualization import MacroVisualizer
    
    viz = MacroVisualizer()
    fig = viz.create_trend_chart(official_df, personal_df)
"""

import os
import sys
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# TCMB RAPOR STİLİ RENK PALETİ
# ============================================================================

TCMB_COLORS = {
    'primary': '#1A1A5E',      # TCMB Koyu Mavi
    'secondary': '#CC0000',     # TCMB Kırmızı
    'accent': '#4169E1',        # Royal Blue
    'positive': '#28A745',      # Yeşil
    'negative': '#DC3545',      # Kırmızı
    'neutral': '#6C757D',       # Gri
    'background': '#F8F9FA',    # Açık Gri
    
    # Kategori renkleri
    'official': '#CC0000',      # Resmi enflasyon - Kırmızı
    'personal': '#4169E1',      # Kişisel enflasyon - Mavi
    'core': '#28A745',          # Çekirdek enflasyon - Yeşil
    'food': '#FF8C00',          # Gıda - Turuncu
    'housing': '#9370DB',       # Konut - Mor
    'transport': '#20B2AA',     # Ulaştırma - Turkuaz
}

# Isı haritası renk skalası
HEATMAP_COLORSCALE = [
    [0.0, '#00FF00'],    # Yeşil (düşük)
    [0.25, '#FFFF00'],   # Sarı
    [0.5, '#FFA500'],    # Turuncu
    [0.75, '#FF4500'],   # Kırmızı-Turuncu
    [1.0, '#FF0000']     # Kırmızı (yüksek)
]


class MacroVisualizer:
    """
    TCMB rapor stilinde makro ekonomik grafikler üreten sınıf.
    """
    
    def __init__(self, theme: str = "tcmb"):
        """
        Args:
            theme: Görsel tema ("tcmb", "dark", "light")
        """
        self.theme = theme
        self.colors = TCMB_COLORS
    
    def create_trend_chart(self, 
                           official_data: pd.DataFrame,
                           personal_data: pd.DataFrame = None,
                           title: str = "Enflasyon Trendi (Son 5 Yıl)") -> go.Figure:
        """
        Resmi ve kişisel enflasyonu karşılaştıran trend grafiği.
        
        Args:
            official_data: EVDS'den çekilmiş resmi enflasyon verisi
                          Kolonlar: ['Tarih', 'Genel TÜFE', ...]
            personal_data: Kişisel enflasyon verisi (opsiyonel)
                          Kolonlar: ['Tarih', 'Kisisel_Enflasyon']
            title: Grafik başlığı
        
        Returns:
            Plotly Figure
        """
        fig = go.Figure()
        
        # Resmi Enflasyon (Kırmızı)
        if 'Genel TÜFE' in official_data.columns:
            fig.add_trace(go.Scatter(
                x=official_data['Tarih'],
                y=official_data['Genel TÜFE'],
                mode='lines+markers',
                name='Resmi Enflasyon (TÜFE)',
                line=dict(color=self.colors['official'], width=3),
                marker=dict(size=6),
                hovertemplate='%{x|%B %Y}<br>Resmi: %{y:.1f}%<extra></extra>'
            ))
        
        # Çekirdek Enflasyon (Yeşil)
        if 'B Endeksi (Çekirdek)' in official_data.columns:
            fig.add_trace(go.Scatter(
                x=official_data['Tarih'],
                y=official_data['B Endeksi (Çekirdek)'],
                mode='lines',
                name='Çekirdek Enflasyon (B)',
                line=dict(color=self.colors['core'], width=2, dash='dash'),
                hovertemplate='%{x|%B %Y}<br>Çekirdek: %{y:.1f}%<extra></extra>'
            ))
        
        # Kişisel Enflasyon (Mavi)
        if personal_data is not None and 'Kisisel_Enflasyon' in personal_data.columns:
            fig.add_trace(go.Scatter(
                x=personal_data['Tarih'],
                y=personal_data['Kisisel_Enflasyon'],
                mode='lines+markers',
                name='Kişisel Enflasyonum',
                line=dict(color=self.colors['personal'], width=3),
                marker=dict(size=8, symbol='diamond'),
                hovertemplate='%{x|%B %Y}<br>Kişisel: %{y:.1f}%<extra></extra>'
            ))
        
        # Layout
        fig.update_layout(
            title=dict(
                text=f"📈 {title}",
                font=dict(size=20, color=self.colors['primary']),
                x=0.5
            ),
            xaxis=dict(
                title="Tarih",
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                tickformat='%b %Y'
            ),
            yaxis=dict(
                title="Enflasyon (%)",
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                ticksuffix='%'
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            ),
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=500
        )
        
        # Önemli olayları işaretle (örnek)
        fig.add_annotation(
            x=official_data['Tarih'].iloc[-1],
            y=official_data['Genel TÜFE'].iloc[-1] if 'Genel TÜFE' in official_data.columns else 0,
            text=f"Son: %{official_data['Genel TÜFE'].iloc[-1]:.1f}" if 'Genel TÜFE' in official_data.columns else "",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor=self.colors['official'],
            font=dict(size=12, color=self.colors['official'])
        )
        
        return fig
    
    def create_heatmap(self, 
                       data: pd.DataFrame,
                       value_column: str = 'Genel TÜFE',
                       title: str = "Aylık Enflasyon Isı Haritası") -> go.Figure:
        """
        Aylara göre enflasyon yoğunluğunu gösteren ısı haritası.
        
        Args:
            data: Enflasyon verisi (Tarih kolonu datetime olmalı)
            value_column: Değer kolonu
            title: Grafik başlığı
        
        Returns:
            Plotly Figure
        """
        # Veriyi pivot tabloya çevir (Yıl x Ay)
        df = data.copy()
        df['Yıl'] = df['Tarih'].dt.year
        df['Ay'] = df['Tarih'].dt.month
        
        # Ay isimleri
        ay_isimleri = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz',
                       'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
        
        # Pivot tablo
        pivot = df.pivot_table(
            values=value_column,
            index='Yıl',
            columns='Ay',
            aggfunc='mean'
        )
        
        # Kolon isimlerini değiştir
        pivot.columns = [ay_isimleri[i-1] for i in pivot.columns]
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=HEATMAP_COLORSCALE,
            hovertemplate='%{y} %{x}<br>Enflasyon: %{z:.1f}%<extra></extra>',
            colorbar=dict(
                title='Enflasyon (%)',
                ticksuffix='%'
            )
        ))
        
        # Değerleri hücrelere yaz
        for i, year in enumerate(pivot.index):
            for j, month in enumerate(pivot.columns):
                value = pivot.iloc[i, j]
                if not pd.isna(value):
                    fig.add_annotation(
                        x=month,
                        y=year,
                        text=f"{value:.0f}",
                        showarrow=False,
                        font=dict(
                            color='white' if value > 50 else 'black',
                            size=10
                        )
                    )
        
        fig.update_layout(
            title=dict(
                text=f"🌡️ {title}",
                font=dict(size=20, color=self.colors['primary']),
                x=0.5
            ),
            xaxis=dict(title="Ay", side="bottom"),
            yaxis=dict(title="Yıl", autorange="reversed"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=400
        )
        
        return fig
    
    def create_spread_chart(self,
                            official_data: pd.DataFrame,
                            personal_data: pd.DataFrame,
                            title: str = "Enflasyon Makası (Kişisel - Resmi)") -> go.Figure:
        """
        Kişisel ve resmi enflasyon arasındaki farkı gösteren çubuk grafik.
        
        Args:
            official_data: Resmi enflasyon verisi
            personal_data: Kişisel enflasyon verisi
            title: Grafik başlığı
        
        Returns:
            Plotly Figure
        """
        # Verileri birleştir
        merged = pd.merge(
            official_data[['Tarih', 'Genel TÜFE']],
            personal_data[['Tarih', 'Kisisel_Enflasyon']],
            on='Tarih',
            how='inner'
        )
        
        # Farkı hesapla
        merged['Fark'] = merged['Kisisel_Enflasyon'] - merged['Genel TÜFE']
        
        # Renkleri belirle (pozitif: kırmızı, negatif: yeşil)
        colors = [self.colors['negative'] if x > 0 else self.colors['positive'] 
                  for x in merged['Fark']]
        
        fig = go.Figure()
        
        # Çubuk grafik
        fig.add_trace(go.Bar(
            x=merged['Tarih'],
            y=merged['Fark'],
            marker_color=colors,
            hovertemplate=(
                '%{x|%B %Y}<br>'
                'Fark: %{y:+.1f} puan<br>'
                '<extra></extra>'
            ),
            name='Fark'
        ))
        
        # Sıfır çizgisi
        fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=2)
        
        # Ortalama fark çizgisi
        avg_spread = merged['Fark'].mean()
        fig.add_hline(
            y=avg_spread,
            line_dash="dash",
            line_color=self.colors['neutral'],
            annotation_text=f"Ort: {avg_spread:+.1f}",
            annotation_position="right"
        )
        
        fig.update_layout(
            title=dict(
                text=f"📊 {title}",
                font=dict(size=20, color=self.colors['primary']),
                x=0.5
            ),
            xaxis=dict(
                title="Tarih",
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                tickformat='%b %Y'
            ),
            yaxis=dict(
                title="Fark (Puan)",
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=True,
                zerolinecolor='black',
                zerolinewidth=2
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=400,
            showlegend=False
        )
        
        # Açıklama notu
        fig.add_annotation(
            x=0.02,
            y=0.98,
            xref="paper",
            yref="paper",
            text="🔴 Kişisel > Resmi | 🟢 Kişisel < Resmi",
            showarrow=False,
            font=dict(size=11),
            bgcolor="white",
            bordercolor="gray",
            borderwidth=1
        )
        
        return fig
    
    def create_category_breakdown(self,
                                   data: pd.DataFrame,
                                   latest_only: bool = True,
                                   title: str = "Kategori Bazlı Enflasyon") -> go.Figure:
        """
        Enflasyon alt kırılımlarını gösteren çubuk grafik.
        
        Args:
            data: EVDS verisi (tüm kategoriler)
            latest_only: Sadece son ayı göster
            title: Grafik başlığı
        
        Returns:
            Plotly Figure
        """
        # Sadece kategori kolonlarını al
        exclude_cols = ['Tarih', 'Genel TÜFE', 'B Endeksi (Çekirdek)', 'C Endeksi (Çekirdek)']
        category_cols = [col for col in data.columns if col not in exclude_cols]
        
        if latest_only:
            df = data.iloc[-1:][category_cols].T
            df.columns = ['Enflasyon']
            df = df.reset_index()
            df.columns = ['Kategori', 'Enflasyon']
            df = df.sort_values('Enflasyon', ascending=True)
        else:
            # Son 12 ayın ortalaması
            df = data.tail(12)[category_cols].mean().reset_index()
            df.columns = ['Kategori', 'Enflasyon']
            df = df.sort_values('Enflasyon', ascending=True)
        
        # Renk paleti - manuel oluştur
        n_colors = len(df)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df['Enflasyon'],
            y=df['Kategori'],
            orientation='h',
            marker=dict(
                color=df['Enflasyon'],
                colorscale='RdYlGn_r',
                showscale=True,
                colorbar=dict(title='%')
            ),
            hovertemplate='%{y}<br>%{x:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title=dict(
                text=f"📋 {title}",
                font=dict(size=20, color=self.colors['primary']),
                x=0.5
            ),
            xaxis=dict(
                title="Enflasyon (%)",
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                ticksuffix='%'
            ),
            yaxis=dict(
                title="",
                showgrid=False
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=500
        )
        
        return fig
    
    def create_dashboard(self,
                         official_data: pd.DataFrame,
                         personal_data: pd.DataFrame = None) -> go.Figure:
        """
        Tüm grafikleri bir dashboard'da birleştirir.
        
        Returns:
            Plotly Figure with subplots
        """
        # 2x2 subplot oluştur
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "📈 Enflasyon Trendi",
                "🌡️ Isı Haritası",
                "📊 Makas Grafiği",
                "📋 Kategori Kırılımı"
            ),
            specs=[
                [{"type": "scatter"}, {"type": "heatmap"}],
                [{"type": "bar"}, {"type": "bar"}]
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.08
        )
        
        # 1. Trend Grafiği
        if 'Genel TÜFE' in official_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=official_data['Tarih'],
                    y=official_data['Genel TÜFE'],
                    mode='lines',
                    name='Resmi',
                    line=dict(color=self.colors['official'], width=2)
                ),
                row=1, col=1
            )
        
        if personal_data is not None and 'Kisisel_Enflasyon' in personal_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=personal_data['Tarih'],
                    y=personal_data['Kisisel_Enflasyon'],
                    mode='lines',
                    name='Kişisel',
                    line=dict(color=self.colors['personal'], width=2)
                ),
                row=1, col=1
            )
        
        # 2. Isı Haritası (basitleştirilmiş)
        if 'Genel TÜFE' in official_data.columns:
            df = official_data.copy()
            df['Yıl'] = df['Tarih'].dt.year
            df['Ay'] = df['Tarih'].dt.month
            
            pivot = df.pivot_table(
                values='Genel TÜFE',
                index='Yıl',
                columns='Ay',
                aggfunc='mean'
            )
            
            fig.add_trace(
                go.Heatmap(
                    z=pivot.values,
                    x=list(range(1, 13)),
                    y=pivot.index.tolist(),
                    colorscale=HEATMAP_COLORSCALE,
                    showscale=False
                ),
                row=1, col=2
            )
        
        # Dashboard layout
        fig.update_layout(
            title=dict(
                text="🏦 Makro Ekonomik Analiz Dashboard",
                font=dict(size=24, color=self.colors['primary']),
                x=0.5
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            ),
            height=800,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return fig


# ============================================================================
# STREAMLIT İÇİN KOLAYLIK FONKSİYONLARI
# ============================================================================

def render_macro_analysis_tab(official_df: pd.DataFrame,
                               personal_df: pd.DataFrame = None):
    """
    Streamlit'te Makro Analiz sekmesini render eder.
    
    Bu fonksiyonu app.py'de kullanın:
        from analysis.macro_visualization import render_macro_analysis_tab
        render_macro_analysis_tab(evds_data, personal_data)
    """
    import streamlit as st
    
    viz = MacroVisualizer()
    
    st.markdown("## 🏦 Makro Ekonomik Analiz")
    st.markdown("---")
    
    # Özet metrikler
    if not official_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        latest = official_df.iloc[-1]
        
        with col1:
            if 'Genel TÜFE' in official_df.columns:
                st.metric(
                    "Manşet Enflasyon",
                    f"%{latest['Genel TÜFE']:.1f}",
                    help="TÜİK TÜFE Yıllık"
                )
        
        with col2:
            if 'B Endeksi (Çekirdek)' in official_df.columns:
                st.metric(
                    "Çekirdek (B)",
                    f"%{latest['B Endeksi (Çekirdek)']:.1f}",
                    help="İşlenmemiş gıda ve enerji hariç"
                )
        
        with col3:
            if 'Gıda ve Alkolsüz İçecekler' in official_df.columns:
                st.metric(
                    "Gıda Enflasyonu",
                    f"%{latest['Gıda ve Alkolsüz İçecekler']:.1f}",
                    help="Mutfak sepeti enflasyonu"
                )
        
        with col4:
            if personal_df is not None and 'Kisisel_Enflasyon' in personal_df.columns:
                personal_latest = personal_df.iloc[-1]['Kisisel_Enflasyon']
                official_latest = latest.get('Genel TÜFE', 0)
                delta = personal_latest - official_latest
                st.metric(
                    "Kişisel Enflasyon",
                    f"%{personal_latest:.1f}",
                    f"{delta:+.1f} puan",
                    delta_color="inverse"
                )
    
    st.markdown("---")
    
    # Tab'lar
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Trend", "🌡️ Isı Haritası", "📊 Makas", "📋 Kategoriler"
    ])
    
    with tab1:
        fig = viz.create_trend_chart(official_df, personal_df)
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        fig = viz.create_heatmap(official_df)
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        if personal_df is not None:
            fig = viz.create_spread_chart(official_df, personal_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 Makas grafiği için kişisel enflasyon verisi gerekli.")
    
    with tab4:
        fig = viz.create_category_breakdown(official_df)
        st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Makro Görselleştirme Modülü Test")
    print("=" * 60)
    
    # Test verisi oluştur
    from scrapers.evds_data import generate_simulated_evds_data
    
    official_df = generate_simulated_evds_data()
    
    # Kişisel veri simülasyonu
    personal_df = official_df[['Tarih', 'Genel TÜFE']].copy()
    personal_df['Kisisel_Enflasyon'] = personal_df['Genel TÜFE'] * np.random.uniform(0.9, 1.1, len(personal_df))
    
    # Grafikleri test et
    viz = MacroVisualizer()
    
    print("\n📈 Trend grafiği oluşturuluyor...")
    fig1 = viz.create_trend_chart(official_df, personal_df)
    
    print("🌡️ Isı haritası oluşturuluyor...")
    fig2 = viz.create_heatmap(official_df)
    
    print("📊 Makas grafiği oluşturuluyor...")
    fig3 = viz.create_spread_chart(official_df, personal_df)
    
    print("📋 Kategori grafiği oluşturuluyor...")
    fig4 = viz.create_category_breakdown(official_df)
    
    print("\n✅ Tüm grafikler başarıyla oluşturuldu!")
    print("💡 Streamlit'te görüntülemek için: streamlit run app.py")
