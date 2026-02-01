import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import twstock
import numpy as np
import matplotlib.pyplot as plt

# --- 1. 頁面設定 ---
st.set_page_config(page_title="股票型態分析", layout="wide")
st.title("📈 股票型態分析")

# --- 2. 側邊欄輸入 ---
with st.sidebar:
    st.header("設定")
    stock_id = st.text_input("輸入股票代號", value="6271.TW") # 預設改成您的範例 6271
    st.caption("範例：2330.TW (上市) / 3491.TWO (上櫃)")
    
    show_lines = st.checkbox("顯示支撐/壓力線 (虛線)", value=True)
    
    run_btn = st.button("開始分析", type="primary")

# --- 3. 核心邏輯 ---

def get_stock_name(symbol):
    try:
        code = symbol.split('.')[0]
        if code in twstock.codes:
            return twstock.codes[code].name
    except: pass
    return symbol

def get_data(symbol):
    try:
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df = df.round(2)
        return df if len(df) > 120 else None
    except: return None

def calculate_kd(df, n=9):
    data = df.copy()
    data['Lowest_Low'] = data['Low'].rolling(window=n).min()
    data['Highest_High'] = data['High'].rolling(window=n).max()
    data['RSV'] = (data['Close'] - data['Lowest_Low']) / (data['Highest_High'] - data['Lowest_Low']) * 100
    data['K'] = 50
    data['D'] = 50
    k_list, d_list = [], []
    k_curr, d_curr = 50, 50
    for rsv in data['RSV']:
        if pd.isna(rsv):
            k_list.append(50)
            d_list.append(50)
        else:
            k_curr = (2/3) * k_curr + (1/3) * rsv
            d_curr = (2/3) * d_curr + (1/3) * k_curr
            k_list.append(k_curr)
            d_list.append(d_curr)
    data['K'] = k_list
    data['D'] = d_list
    return data

def check_patterns(df):
    """偵測技術型態"""
    signals = []
    df_kd = calculate_kd(df)
    today = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. KD 鈍化 (標記用)
    last_3_k = df_kd['K'].iloc[-3:]
    if (last_3_k > 80).all():
        signals.append({"name": "KD High Passivation", "type": "marker", "style": "dot_high"})
    elif (last_3_k < 20).all():
        signals.append({"name": "KD Low Passivation", "type": "marker", "style": "dot_low"})

    # 2. 箱型整理 (Box)
    period_high = df['High'].iloc[-60:-1].max()
    period_low = df['Low'].iloc[-60:-1].min()
    amp = (period_high - period_low) / period_low
    
    if amp < 0.50:
        if today['Close'] > period_high:
            signals.append({"name": "Box Breakout", "duration": 60, "color": "red", "alpha": 0.2})
        elif period_low < today['Close'] < period_high:
            if today['Close'] > (period_low + period_high)/2:
                signals.append({"name": "Box Consolidation", "duration": 60, "color": "orange", "alpha": 0.15})
    
    # 3. W底 / M頭
    recent_low = df['Low'].iloc[-10:].min()
    prev_low = df['Low'].iloc[-60:-20].min()
    recent_high = df['High'].iloc[-10:].max()
    prev_high = df['High'].iloc[-60:-20].max()

    if 0.90 < (recent_low/prev_low) < 1.10 and today['Close'] > recent_low*1.05:
        # W底 -> 藍色
        signals.append({"name": "Double Bottom", "duration": 60, "color": "skyblue", "alpha": 0.2})

    if 0.90 < (recent_high/prev_high) < 1.10:
        if today['Close'] < df['Low'].iloc[-20:].min():
             # M頭 -> 綠色
             signals.append({"name": "Double Top (Sell)", "duration": 60, "color": "lightgreen", "alpha": 0.2})

    # 4. 頭肩底/頂
    data_hs = df.iloc[-60:]
    p1 = data_hs['Low'].iloc[0:20].min()
    p2 = data_hs['Low'].iloc[20:40].min() 
    p3 = data_hs['Low'].iloc[40:].min()
    if (p2 < p1) and (p2 < p3): 
        # 頭肩底 -> 藍色
        signals.append({"name": "Head & Shoulders Bottom", "duration": 60, "color": "skyblue", "alpha": 0.2})

    p1_h = data_hs['High'].iloc[0:20].max()
    p2_h = data_hs['High'].iloc[20:40].max() 
    p3_h = data_hs['High'].iloc[40:].max()
    if (p2_h > p1_h) and (p2_h > p3_h):
        neckline = data_hs['Low'].min()
        if today['Close'] < neckline:
             # 頭肩頂 -> 綠色
             signals.append({"name": "Head & Shoulders Top", "duration": 60, "color": "lightgreen", "alpha": 0.2})

    # 5. 三角收斂
    ma_period = 60
    ma = df['Close'].rolling(ma_period).mean()
    std = df['Close'].rolling(ma_period).std()
    bw = ((ma + 2*std) - (ma - 2*std)) / ma
    
    if bw.iloc[-5:].min() < 0.20:
         # 三角收斂 -> 黃色
         signals.append({"name": "Triangle Squeeze", "duration": 60, "color": "yellow", "alpha": 0.2})

    # 6. 杯柄/圓弧
    data_ch = df.iloc[-120:]
    left_rim = data_ch['High'].iloc[:40].max()
    bottom = data_ch['Low'].iloc[40:100].min()
    right_rim = data_ch['High'].iloc[100:].max()
    if (bottom < left_rim * 0.85) and (0.9 < right_rim/left_rim < 1.1):
        if today['Close'] > right_rim * 0.9:
             signals.append({"name": "Cup & Handle", "duration": 120, "color": "orange", "alpha": 0.15})
    
    mid_low = df['Low'].iloc[-80:-40].mean()
    start_high = df['High'].iloc[-120:-100].mean()
    if (mid_low < start_high * 0.8):
        # 圓弧底 -> 藍色
        signals.append({"name": "Rounding Bottom", "duration": 120, "color": "skyblue", "alpha": 0.2})

    # 7. K線型態
    is_engulfing = (prev['Close'] < prev['Open']) and (today['Close'] > today['Open']) and (today['Close'] > prev['Open']) and (today['Open'] < prev['Close'])
    if is_engulfing: 
        signals.append({"name": "Bullish Engulfing", "type": "marker", "style": "arrow_up"})

    body = abs(today['Close'] - today['Open'])
    lower_shadow = min(today['Close'], today['Open']) - today['Low']
    is_hammer = (lower_shadow > body * 2) and (today['Close'] > prev['Close'])
    if is_hammer: 
        signals.append({"name": "Hammer", "type": "marker", "style": "arrow_up"})

    return signals

# --- 4. 主程式執行 ---
if run_btn or stock_id:
    with st.spinner(f"正在分析 {stock_id} ..."):
        df = get_data(stock_id)
        
        if df is None:
            st.error(f"❌ 找不到 {stock_id} 的資料。")
        else:
            stock_name = get_stock_name(stock_id)
            
            # 成交量顏色
            prev_close = df['Close'].shift(1).fillna(0)
            def get_vol_color(row):
                if row['Close'] > row['PrevClose']: return 'red'
                elif row['Close'] < row['PrevClose']: return 'green'
                else: return 'red' if row['Close'] >= row['Open'] else 'green'
            
            temp_df = pd.DataFrame({'Close': df['Close'], 'Open': df['Open'], 'PrevClose': prev_close})
            df['VolColor'] = temp_df.apply(get_vol_color, axis=1)

            plot_data = df.iloc[-120:]
            vol_colors = plot_data['VolColor'].tolist()

            last_price = plot_data['Close'].iloc[-1]
            last_vol = plot_data['Volume'].iloc[-1]
            last_change = last_price - plot_data['Close'].iloc[-2]
            pct_change = (last_change / plot_data['Close'].iloc[-2]) * 100
            
            st.subheader(f"{stock_name} ({stock_id})")
            col1, col2, col3 = st.columns(3)
            col1.metric("收盤價", f"{last_price:.2f}", f"{last_change:.2f} ({pct_change:.2f}%)")
            col2.metric("成交量", f"{int(last_vol/1000)} 張")
            col3.markdown(f"**資料日期**: {plot_data.index[-1].date()}")
            
            signals = check_patterns(df)
            
            mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='inherit')
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
            
            ap = []
            
            name_map = {
                "Box Breakout": "箱型突破", "Box Consolidation": "箱型整理中", "Double Bottom": "W底", 
                "Double Top (Sell)": "M頭(賣訊)", "Head & Shoulders Bottom": "頭肩底", 
                "Head & Shoulders Top": "頭肩頂(賣訊)", "Triangle Squeeze": "三角收斂", 
                "Cup & Handle": "杯柄型態", "Rounding Bottom": "圓弧底", "Bullish Engulfing": "長紅吞噬", "Hammer": "錘頭線",
                "KD High Passivation": "🔥 KD高檔鈍化", "KD Low Passivation": "⚠️ KD低檔鈍化"
            }

            if signals:
                display_names = [name_map.get(s['name'], s['name']) for s in signals if 'name' in s]
                warn_signals = ["Double Top (Sell)", "Head & Shoulders Top", "KD Low Passivation"]
                is_danger = any(s['name'] in warn_signals for s in signals)
                if is_danger:
                    st.error(f"⚠️ 警告訊號：{' + '.join(display_names)}")
                else:
                    st.success(f"🔥 發現訊號：{' + '.join(display_names)}")
                
                eng_names = [s['name'] for s in signals]
                title_text = f"{stock_id} Pattern: {' + '.join(eng_names)}"
            else:
                st.info("👀 目前無特定型態。")
                title_text = f"{stock_id} Analysis"

            # --- 準備標記資料 ---
            marker_series_up = [np.nan] * len(plot_data)
            marker_series_down = [np.nan] * len(plot_data)
            marker_series_dot_high = [np.nan] * len(plot_data)
            marker_series_dot_low = [np.nan] * len(plot_data)
            
            has_marker = False
            for sig in signals:
                if sig.get('type') == 'marker':
                    has_marker = True
                    idx = -1 
                    if sig['style'] == 'arrow_up':
                        marker_series_up[idx] = plot_data['Low'].iloc[idx] * 0.99 
                    elif sig['style'] == 'arrow_down':
                        marker_series_down[idx] = plot_data['High'].iloc[idx] * 1.01
                    elif sig['style'] == 'dot_high':
                        marker_series_dot_high[idx] = plot_data['High'].iloc[idx] * 1.02
                    elif sig['style'] == 'dot_low':
                        marker_series_dot_low[idx] = plot_data['Low'].iloc[idx] * 0.98

            if has_marker:
                if not np.all(np.isnan(marker_series_up)):
                    ap.append(mpf.make_addplot(marker_series_up, type='scatter', markersize=100, marker='^', color='red'))
                if not np.all(np.isnan(marker_series_down)):
                    ap.append(mpf.make_addplot(marker_series_down, type='scatter', markersize=100, marker='v', color='green'))
                if not np.all(np.isnan(marker_series_dot_high)):
                    ap.append(mpf.make_addplot(marker_series_dot_high, type='scatter', markersize=80, marker='o', color='purple'))
                if not np.all(np.isnan(marker_series_dot_low)):
                    ap.append(mpf.make_addplot(marker_series_dot_low, type='scatter', markersize=80, marker='o', color='blue'))

            # --- 繪圖區 ---
            ap.append(mpf.make_addplot(plot_data['Volume'], type='bar', panel=1, color=vol_colors, ylabel='Volume'))

            plot_args = dict(
                type='candle', style=s, volume=False, mav=(5, 20, 60), 
                title=title_text, returnfig=True, panel_ratios=(3, 1)
            )
            
            # --- 支撐/壓力線 ---
            if show_lines:
                short_high = df['High'].iloc[-20:].max()
                short_low = df['Low'].iloc[-20:].min()
                medium_high = df['High'].iloc[-60:].max()
                medium_low = df['Low'].iloc[-60:].min()
                lines = [short_high, short_low, medium_high, medium_low]
                colors = ['orange', 'skyblue', 'red', 'blue']
                plot_args['hlines'] = dict(hlines=lines, colors=colors, linestyle='-.', linewidths=1.0, alpha=0.7)
            
            if ap: plot_args['addplot'] = ap

            fig, axlist = mpf.plot(plot_data, **plot_args)
            ax_main = axlist[0] 

            # --- 【關鍵修正】繪製背景色塊 (防止顏色疊加變深) ---
            total_len = len(plot_data)
            drawn_zones = [] # 記錄已經畫過的區域 (start, end, color)
            
            for sig in signals:
                if 'duration' in sig:
                    duration = sig['duration']
                    color = sig.get('color', 'gray')
                    alpha = sig.get('alpha', 0.1)
                    
                    x_end = total_len - 1
                    x_start = max(0, x_end - duration)
                    
                    # 檢查是否重複畫過相同的顏色與區間 (避免 W底+頭肩底 疊加變成紫色)
                    zone_key = (x_start, x_end, color)
                    if zone_key not in drawn_zones:
                        ax_main.axvspan(x_start, x_end, facecolor=color, alpha=alpha)
                        drawn_zones.append(zone_key)

            st.pyplot(fig)

            # --- 說明區 (完全還原版) ---
            st.markdown("---")
            st.markdown("""
            ### 📝 圖表判讀說明 (完整詳細版)

            #### 1. 🔍 型態偵測區間與邏輯詳解
            本系統依據不同時間週期的 K 線結構進行型態識別：
            
            * ** KD 鈍化 (極端趨勢)**：
                * **🔥 高檔鈍化** (K > 80 連 3 日)：顯示多頭氣勢極強，股價可能沿著布林通道上軌噴出，但也需留意過熱拉回。
                * **⚠️ 低檔鈍化** (K < 20 連 3 日)：顯示空頭氣勢極弱，股價可能沿著布林通道下軌殺盤，但也可能隨時出現反彈。
            
            * ** 短期型態 (K線轉折)**
                * **偵測區間**：過去 2 天
                * **包含型態**：長紅吞噬 (Bullish Engulfing)、錘頭線 (Hammer)
                * **邏輯**：僅比較「今天」與「昨天」的開盤、收盤、最高與最低價，用來捕捉極短線的轉折訊號。

            * ** 中期波段型態 (最常用)**
                * **偵測區間**：過去 60 個交易日 (約 3 個月 / 一季)
                * **包含型態**：
                    * **箱型整理/突破**：計算過去 60 天的高低點區間，若波動幅度 < 50% 且股價在區間內震盪，視為箱型整理。
                    * **W 底 / M 頭**：比較「最近 10 天」與「20~60 天前」的低點(或高點)位置，確認是否形成雙重底或雙重頂。
                    * **頭肩底 / 頭肩頂**：將過去 60 天分為三段 (左肩、頭、右肩) 來比較高低點相對位置。
                    * **三角收斂**：計算布林通道 (60日均線標準差) 的壓縮程度，若近 5 日頻寬低於 20%，代表波段即將變盤。

            * ** 長期大底型態**
                * **偵測區間**：過去 120 個交易日 (約 6 個月 / 半年)
                * **包含型態**：
                    * **杯柄型態 (Cup & Handle)**：因為杯子結構需要時間打底，故抓 120 天來確認左杯緣、杯底和右杯緣的結構。
                    * **圓弧底 (Rounding Bottom)**：同樣需要長時間沉澱，比較 120 天內的頭尾與中間低點，確認是否呈現圓弧狀。

            #### 2. 🎨 型態背景顏色意義 (Pattern Zones)
            當偵測到特定型態時，該時間段的背景會顯示對應顏色，方便一眼識別目前處於何種位階：
            * **🟨 黃色背景**：**三角收斂區**。代表股價波動壓縮至極致，多空即將表態，通常伴隨成交量萎縮。
            * **🟧 橘色背景**：**箱型整理 / 杯柄型態**。股價在特定區間內上下震盪，方向尚未明確。
            * **🟥 紅色背景**：**突破訊號**。股價帶量衝出整理區間，視為強勢多頭訊號。
            * **🟦 藍色背景**：**底部型態** (W底、頭肩底、圓弧底)。代表打底完成，下方支撐強勁。
            * **🟩 綠色背景**：**頭部型態** (M頭、頭肩頂)。代表高檔做頭完成，上方壓力沉重，小心回檔。

            #### 3. 🎯 特殊訊號標記 (Markers)
            * **🔺 紅色向上箭頭**：K線轉折訊號 (錘頭線、長紅吞噬)，暗示短線有止跌反彈契機。
            * **🟣 紫色圓點**：**KD 高檔鈍化**。多頭強勢指標。
            * **🔵 藍色圓點**：**KD 低檔鈍化**。空頭弱勢指標。

            #### 4. 🛡️ 支撐與壓力線 (虛線)
            * **短線 (20日)**：🔸 淺橘虛線 (壓力) / 🔹 淺藍虛線 (支撐)
            * **波段 (60日)**：🔴 深紅虛線 (壓力) / 🔵 深藍虛線 (支撐)

            #### 5. 📈 均線代表
            * 🟦 **藍線 5日** (週線)：短線強弱分界。
            * 🟧 **橘線 20日** (月線)：中線多空生命線。
            * 🟩 **綠線 60日** (季線)：長線趨勢方向。
            """)
