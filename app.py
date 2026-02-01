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
    stock_id = st.text_input("輸入股票代號", value="2359.TW") 
    st.caption("範例：2330.TW (上市) / 3491.TWO (上櫃)")
    
    # 選項：是否顯示支撐壓力線
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
    """偵測技術型態，回傳型態名稱、持續天數、顏色"""
    signals = []
    df_kd = calculate_kd(df)
    today = df.iloc[-1]
    
    # 1. KD 鈍化
    last_3_k = df_kd['K'].iloc[-3:]
    if (last_3_k > 80).all():
        signals.append({"name": "KD High Passivation", "type": "text"})
    elif (last_3_k < 20).all():
        signals.append({"name": "KD Low Passivation", "type": "text"})

    # 2. 箱型整理 (Box) - 60天
    period_high = df['High'].iloc[-60:-1].max()
    period_low = df['Low'].iloc[-60:-1].min()
    amp = (period_high - period_low) / period_low
    
    if amp < 0.50:
        if today['Close'] > period_high:
            signals.append({"name": "Box Breakout", "duration": 60, "color": "red", "alpha": 0.2})
        elif period_low < today['Close'] < period_high:
            if today['Close'] > (period_low + period_high)/2:
                signals.append({"name": "Box Consolidation", "duration": 60, "color": "orange", "alpha": 0.15})
    
    # 3. W底 / M頭 - 60天
    recent_low = df['Low'].iloc[-10:].min()
    prev_low = df['Low'].iloc[-60:-20].min()
    recent_high = df['High'].iloc[-10:].max()
    prev_high = df['High'].iloc[-60:-20].max()

    if 0.90 < (recent_low/prev_low) < 1.10 and today['Close'] > recent_low*1.05:
        signals.append({"name": "Double Bottom", "duration": 60, "color": "blue", "alpha": 0.15})

    if 0.90 < (recent_high/prev_high) < 1.10:
        if today['Close'] < df['Low'].iloc[-20:].min():
             signals.append({"name": "Double Top (Sell)", "duration": 60, "color": "green", "alpha": 0.15})

    # 4. 頭肩底/頂 - 60天
    data_hs = df.iloc[-60:]
    p1 = data_hs['Low'].iloc[0:20].min()
    p2 = data_hs['Low'].iloc[20:40].min() 
    p3 = data_hs['Low'].iloc[40:].min()
    
    if (p2 < p1) and (p2 < p3): 
        signals.append({"name": "Head & Shoulders Bottom", "duration": 60, "color": "blue", "alpha": 0.15})

    p1_h = data_hs['High'].iloc[0:20].max()
    p2_h = data_hs['High'].iloc[20:40].max() 
    p3_h = data_hs['High'].iloc[40:].max()
    
    if (p2_h > p1_h) and (p2_h > p3_h):
        neckline = data_hs['Low'].min()
        if today['Close'] < neckline:
             signals.append({"name": "Head & Shoulders Top", "duration": 60, "color": "green", "alpha": 0.15})

    # 5. 三角收斂 (60天大收斂)
    ma_period = 60
    ma = df['Close'].rolling(ma_period).mean()
    std = df['Close'].rolling(ma_period).std()
    bw = ((ma + 2*std) - (ma - 2*std)) / ma
    
    if bw.iloc[-5:].min() < 0.20:
         # 三角收斂使用黃色背景
         signals.append({
             "name": "Triangle Squeeze", 
             "duration": 60, 
             "color": "yellow", 
             "alpha": 0.2
         })

    # 6. 杯柄/圓弧 - 120天
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
        signals.append({"name": "Rounding Bottom", "duration": 120, "color": "blue", "alpha": 0.15})

    return signals

# --- 4. 主程式執行 ---
if run_btn or stock_id:
    with st.spinner(f"正在分析 {stock_id} ..."):
        df = get_data(stock_id)
        
        if df is None:
            st.error(f"❌ 找不到 {stock_id} 的資料。")
        else:
            stock_name = get_stock_name(stock_id)
            
            # 成交量顏色 (精準券商版)
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
                "Cup & Handle": "杯柄型態", "Rounding Bottom": "圓弧底",
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

            # --- 繪圖區 ---
            ap.append(mpf.make_addplot(plot_data['Volume'], type='bar', panel=1, color=vol_colors, ylabel='Volume'))

            plot_args = dict(
                type='candle', style=s, volume=False, mav=(5, 20, 60), 
                title=title_text, returnfig=True, panel_ratios=(3, 1)
            )
            
            # --- 支撐/壓力線 (還原) ---
            if show_lines:
                short_high = df['High'].iloc[-20:].max()
                short_low = df['Low'].iloc[-20:].min()
                medium_high = df['High'].iloc[-60:].max()
                medium_low = df['Low'].iloc[-60:].min()
                
                # 設定線條：短線(橘/淺藍), 中線(紅/深藍)
                lines = [short_high, short_low, medium_high, medium_low]
                colors = ['orange', 'skyblue', 'red', 'blue']
                
                plot_args['hlines'] = dict(hlines=lines, colors=colors, linestyle='-.', linewidths=1.0, alpha=0.7)
            
            if ap: plot_args['addplot'] = ap

            fig, axlist = mpf.plot(plot_data, **plot_args)
            ax_main = axlist[0] 

            # --- 繪製全版背景色塊 (Vertical Span) ---
            total_len = len(plot_data)
            
            for sig in signals:
                if 'duration' in sig:
                    duration = sig['duration']
                    color = sig.get('color', 'gray')
                    alpha = sig.get('alpha', 0.1)
                    
                    # 計算 x 軸範圍 (從最後一天往回推 duration 天)
                    x_end = total_len - 1
                    x_start = max(0, x_end - duration)
                    
                    # 使用 axvspan 繪製垂直背景色塊 (涵蓋整個上下範圍)
                    ax_main.axvspan(x_start, x_end, facecolor=color, alpha=alpha)

            st.pyplot(fig)

            # --- 說明區 (完全還原詳細版) ---
            st.markdown("---")
            st.markdown("""
            ### 📝 圖表判讀說明

            #### 1. 🔍 型態偵測區間詳解
            * ** KD 鈍化 (極端趨勢)**：
                * **🔥 高檔鈍化** (K > 80 連 3 日)：多頭極強，行情可能噴出。
                * **⚠️ 低檔鈍化** (K < 20 連 3 日)：空頭極弱，小心殺盤重心。
            * ** 短期型態 (K線轉折)**
                * **偵測區間**：過去 2 天
                * **包含型態**：長紅吞噬 (Bullish Engulfing)、錘頭線 (Hammer)
                * **邏輯**：只比較「今天」與「昨天」的開盤、收盤與最高最低價，用來抓極短線轉折。
            * ** 中期波段型態 (最常用)**
                * **偵測區間**：過去 60 個交易日 (約 3 個月 / 一季)
                * **包含型態**：
                    * **箱型整理/突破**：看過去 60 天的高低點區間，波動 < 50%。
                    * **W 底 / M 頭**：比較「最近 10 天」與「20~60 天前」的低點/高點位置。
                    * **頭肩底 / 頭肩頂**：將過去 60 天分為三段 (左肩、頭、右肩) 來比較。
                    * **三角收斂**：計算布林通道 (60日均線標準差) 的壓縮程度 (近5日低於20%)。
            * ** 長期大底型態**
                * **偵測區間**：過去 120 個交易日 (約 6 個月 / 半年)
                * **包含型態**：
                    * **杯柄型態 (Cup & Handle)**：因為杯子需要時間打底，所以抓 120 天來確認左杯緣、杯底和右杯緣。
                    * **圓弧底 (Rounding Bottom)**：同樣需要長時間沉澱，所以比較 120 天內的頭尾與中間低點。

            #### 2. 🎨 型態背景顏色意義 (Pattern Zones)
            當偵測到特定型態時，該時間段的背景會顯示對應顏色：
            * **🟨 黃色背景**：**三角收斂區**。股價波動壓縮，多空即將表態。
            * **🟧 橘色背景**：**箱型整理 / 杯柄**。股價在區間內震盪。
            * **🟥 紅色背景**：**突破訊號**。股價轉強，突破整理區間。
            * **🟦 藍色背景**：**底部型態** (W底、頭肩底、圓弧底)。打底完成，支撐強勁。
            * **🟩 綠色背景**：**頭部型態** (M頭、頭肩頂)。高檔做頭，小心回檔。

            #### 3. 🛡️ 支撐與壓力線 (虛線)
            * **短線 (20日)**：🔸 淺橘虛線 (壓力) / 🔹 淺藍虛線 (支撐)
            * **波段 (60日)**：🔴 深紅虛線 (壓力) / 🔵 深藍虛線 (支撐)

            #### 4. 📈 均線代表
            * 🟦 **藍線 5日** (週線) / 🟧 **橘線 20日** (月線) / 🟩 **綠線 60日** (季線)。
            """)
