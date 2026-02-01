import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import twstock

# --- 1. 頁面設定 ---
st.set_page_config(page_title="股票型態分析", layout="wide")
st.title("📈 股票型態分析")

# --- 2. 側邊欄輸入 ---
with st.sidebar:
    st.header("設定")
    stock_id = st.text_input("輸入股票代號", value="3060.TW") 
    st.caption("範例：2330.TW (上市) / 3491.TWO (上櫃)")
    
    # 功能開關
    show_sr = st.checkbox("顯示支撐/壓力線", value=True)
    
    run_btn = st.button("開始分析", type="primary")

# --- 3. 核心邏輯 ---

def get_stock_name(symbol):
    """取得股票中文名稱"""
    try:
        code = symbol.split('.')[0]
        if code in twstock.codes:
            return twstock.codes[code].name
    except: pass
    return symbol

def get_data(symbol):
    """下載股價資料"""
    try:
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df if len(df) > 120 else None
    except: return None

def calculate_kd(df, n=9):
    """計算 KD 指標"""
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
    """偵測各種技術型態"""
    signals = []
    df_kd = calculate_kd(df)
    today = df.iloc[-1]
    prev = df.iloc[-2]
    
    # --- A. KD 鈍化 ---
    last_3_k = df_kd['K'].iloc[-3:]
    if (last_3_k > 80).all():
        signals.append({"name": "KD High Passivation", "type": "text"})
    elif (last_3_k < 20).all():
        signals.append({"name": "KD Low Passivation", "type": "text"})

    # --- B. 結構型態 (畫線) ---
    
    # 1. 箱型整理/突破
    period_high = df['High'].iloc[-60:-1].max()
    period_low = df['Low'].iloc[-60:-1].min()
    amp = (period_high - period_low) / period_low
    
    if amp < 0.25:
        if today['Close'] > period_high:
            signals.append({"name": "Box Breakout", "type": "box", "levels": [period_high, period_low], "colors": ['red', 'green']})
        elif period_low < today['Close'] < period_high:
            if today['Close'] > (period_low + period_high)/2:
                signals.append({"name": "Box Consolidation", "type": "box", "levels": [period_high, period_low], "colors": ['orange', 'blue']})
    
    # 2. W底
    recent_low = df['Low'].iloc[-10:].min()
    prev_low = df['Low'].iloc[-60:-20].min()
    if 0.97 < (recent_low/prev_low) < 1.03 and today['Close'] > recent_low*1.02:
        signals.append({"name": "Double Bottom", "type": "line", "levels": [recent_low], "colors": ['blue']})

    # 3. M頭 (賣訊)
    recent_high = df['High'].iloc[-10:].max()
    prev_high = df['High'].iloc[-60:-20].max()
    if 0.97 < (recent_high/prev_high) < 1.03:
        if today['Close'] < df['Low'].iloc[-20:].min():
             signals.append({"name": "Double Top (Sell)", "type": "line", "levels": [recent_high], "colors": ['green']})

    # 4a. 頭肩底
    data_hs = df.iloc[-60:]
    p1 = data_hs['Low'].iloc[0:20].min()
    p2 = data_hs['Low'].iloc[20:40].min()
    p3 = data_hs['Low'].iloc[40:].min()
    if (p2 < p1) and (p2 < p3) and (0.9 < p1/p3 < 1.1):
        signals.append({"name": "Head & Shoulders Bottom", "type": "line", "levels": [p2], "colors": ['blue']})

    # 4b. 頭肩頂
    p1_h = data_hs['High'].iloc[0:20].max()
    p2_h = data_hs['High'].iloc[20:40].max() 
    p3_h = data_hs['High'].iloc[40:].max()
    if (p2_h > p1_h) and (p2_h > p3_h):
        neckline = data_hs['Low'].min()
        if today['Close'] < neckline:
             signals.append({"name": "Head & Shoulders Top", "type": "line", "levels": [p2_h], "colors": ['green']})

    # 5. 三角收斂
    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    bw = ((ma20+2*std20) - (ma20-2*std20))/ma20
    if bw.iloc[-5:].min() < 0.13:
         signals.append({"name": "Triangle Squeeze", "type": "bollinger", "data": [ma20+2*std20, ma20-2*std20]})

    # 6. 杯柄
    data_ch = df.iloc[-120:]
    left_rim = data_ch['High'].iloc[:40].max()
    bottom = data_ch['Low'].iloc[40:100].min()
    right_rim = data_ch['High'].iloc[100:].max()
    if (bottom < left_rim * 0.85) and (0.9 < right_rim/left_rim < 1.1):
        if today['Close'] > right_rim * 0.9:
            signals.append({"name": "Cup & Handle", "type": "line", "levels": [left_rim], "colors": ['orange']})

    # 7. 圓弧底
    mid_low = df['Low'].iloc[-80:-40].mean()
    start_high = df['High'].iloc[-120:-100].mean()
    end_high = df['High'].iloc[-20:].mean()
    if (mid_low < start_high * 0.8) and (abs(start_high - end_high) / start_high < 0.1):
        signals.append({"name": "Rounding Bottom", "type": "line", "levels": [mid_low], "colors": ['blue']})

    # --- C. K線型態 ---
    
    # 8. 長紅吞噬
    is_engulfing = (prev['Close'] < prev['Open']) and (today['Close'] > today['Open']) and (today['Close'] > prev['Open']) and (today['Open'] < prev['Close'])
    if is_engulfing: 
        signals.append({"name": "Bullish Engulfing", "type": "line", "levels": [today['High']], "colors": ['red']})

    # 9. 錘頭線
    body = abs(today['Close'] - today['Open'])
    lower_shadow = min(today['Close'], today['Open']) - today['Low']
    is_hammer = (lower_shadow > body * 2) and (today['Close'] > prev['Close'])
    if is_hammer: 
        signals.append({"name": "Hammer", "type": "line", "levels": [today['High']], "colors": ['red']})

    return signals

# --- 4. 主程式執行 ---
if run_btn or stock_id:
    with st.spinner(f"正在分析 {stock_id} ..."):
        df = get_data(stock_id)
        
        if df is None:
            st.error(f"❌ 找不到 {stock_id} 的資料，請確認代號是否正確。")
        else:
            stock_name = get_stock_name(stock_id)
            last_price = df['Close'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            change = last_price - df['Close'].iloc[-2]
            pct_change = (change / df['Close'].iloc[-2]) * 100
            
            # 顯示資訊看板
            st.subheader(f"{stock_name} ({stock_id})")
            col1, col2, col3 = st.columns(3)
            col1.metric("收盤價", f"{last_price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            col2.metric("成交量", f"{int(last_vol/1000)} 張")
            col3.markdown(f"**資料日期**: {df.index[-1].date()}")
            
            # 執行型態偵測
            signals = check_patterns(df)
            
            # 設定台股配色
            mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='inherit')
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
            
            ap = []
            h_lines = []
            h_colors = []
            title_text = f"{stock_id} Analysis"
            
            # 中文名稱對照表
            name_map = {
                "Box Breakout": "箱型突破", 
                "Box Consolidation": "箱型整理中",
                "Double Bottom": "W底", 
                "Double Top (Sell)": "M頭(賣訊)",
                "Head & Shoulders Bottom": "頭肩底", 
                "Head & Shoulders Top": "頭肩頂(賣訊)",
                "Triangle Squeeze": "三角收斂", 
                "Cup & Handle": "杯柄型態",
                "Rounding Bottom": "圓弧底", 
                "Bullish Engulfing": "長紅吞噬", 
                "Hammer": "錘頭線",
                "KD High Passivation": "🔥 KD高檔鈍化(強勢)",
                "KD Low Passivation": "⚠️ KD低檔鈍化(弱勢)"
            }

            if signals:
                display_names = [name_map.get(s['name'], s['name']) for s in signals]
                warn_signals = ["Double Top (Sell)", "Head & Shoulders Top", "KD Low Passivation"]
                is_danger = any(s['name'] in warn_signals for s in signals)
                
                if is_danger:
                    st.error(f"⚠️ 警告訊號：{' + '.join(display_names)}")
                else:
                    st.success(f"🔥 發現訊號：{' + '.join(display_names)}")
                
                eng_names = [s['name'] for s in signals]
                title_text = f"{stock_id} Pattern: {' + '.join(eng_names)}"
                
                for sig in signals:
                    if 'levels' in sig:
                        h_lines.extend(sig['levels'])
                        h_colors.extend(sig['colors'])
                    if sig.get('type') == 'bollinger':
                        ap.append(mpf.make_addplot(sig['data'][0].iloc[-120:], color='gray', alpha=0.5))
                        ap.append(mpf.make_addplot(sig['data'][1].iloc[-120:], color='gray', alpha=0.5))
            else:
                st.info("👀 目前無特定型態。")

            # --- 自動畫支撐/壓力線邏輯 ---
            if show_sr or not h_lines:
                short_high = df['High'].iloc[-20:].max()
                short_low = df['Low'].iloc[-20:].min()
                medium_high = df['High'].iloc[-60:].max()
                medium_low = df['Low'].iloc[-60:].min()
                
                if abs(short_high - medium_high) / medium_high > 0.02:
                    h_lines.append(short_high)
                    h_colors.append('orange') 
                h_lines.append(medium_high)
                h_colors.append('red') 
                
                if abs(short_low - medium_low) / medium_low > 0.02:
                    h_lines.append(short_low)
                    h_colors.append('skyblue') 
                h_lines.append(medium_low)
                h_colors.append('blue') 
                
                st.caption(f"**短線 (20日)**：{short_high:.2f} (壓力) / {short_low:.2f} (支撐)")
                st.caption(f"**波段 (60日)**：{medium_high:.2f} (壓力) / {medium_low:.2f} (支撐)")

            # --- 繪圖區 (修正成交量顏色) ---
            plot_data = df.iloc[-120:]
            
            # 1. 製作成交量顏色陣列 (漲紅跌綠)
            # 使用 Pandas 原生的 diff() 進行計算，這樣會自動對齊 Index
            # diff() 是 Today - Yesterday
            # 填補 NaN 為 0 (第一筆)
            price_diff = df['Close'].diff().fillna(0)
            
            # 2. 轉換顏色 (整年一起轉，不會錯位)
            # 邏輯：漲或平盤(>=0) -> 紅, 跌(<0) -> 綠
            vol_colors_series = price_diff.apply(lambda x: 'red' if x >= 0 else 'green')
            
            # 3. 最後再切片取出這 120 天的顏色
            # 因為 plot_data 是 df 的最後 120 筆，所以顏色也取最後 120 筆
            final_vol_colors = vol_colors_series.iloc[-120:].tolist()

            # 4. 加入成交量副圖
            ap.append(mpf.make_addplot(plot_data['Volume'], type='bar', panel=1, color=final_vol_colors, ylabel='Volume'))

            plot_args = dict(
                type='candle', 
                style=s, 
                volume=False, # 關閉預設，改用上方自定義的 addplot
                mav=(5, 20, 60), 
                title=title_text, 
                returnfig=True,
                panel_ratios=(3, 1)
            )
            
            if h_lines: 
                plot_args['hlines'] = dict(hlines=h_lines, colors=h_colors, linestyle='-.', linewidths=1.5)
            if ap: 
                plot_args['addplot'] = ap

            fig, ax = mpf.plot(plot_data, **plot_args)
            st.pyplot(fig)
            
            # --- 底部說明區 ---
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
                * **邏輯**：抓極短線 K 線轉折訊號。
            * ** 中期波段型態 (最常用)**
                * **偵測區間**：過去 60 個交易日 (約 3 個月 / 一季)
                * **包含型態**：
                    * **箱型整理/突破**：看過去 60 天的高低點區間，波動 < 25%。
                    * **W 底 / M 頭**：比較「最近 10 天」與「20~60 天前」的低點/高點位置。
                    * **頭肩底 / 頭肩頂**：將過去 60 天分為三段 (左肩、頭、右肩) 來比較。
                    * **三角收斂**：計算布林通道 (20日均線標準差) 的壓縮程度 (近5日低於13%)。
            * ** 長期大底型態**
                * **偵測區間**：過去 120 個交易日 (約 6 個月 / 半年)
                * **包含型態**：
                    * **杯柄型態 (Cup & Handle)**：因為杯子需要時間打底，所以抓 120 天來確認左杯緣、杯底和右杯緣。
                    * **圓弧底 (Rounding Bottom)**：同樣需要長時間沉澱，所以比較 120 天內的頭尾與中間低點。

            #### 2. 🎨 線條顏色意義 (型態視覺化)
            * **🟥 紅色 / 🟧 橘色虛線**：壓力線 (箱頂、頸線壓力、K線轉折高點)。
            * **🟦 藍色 / 🟦 淺藍虛線**：支撐線 (箱底、W底支撐、圓弧底)。
            * **🟩 綠色虛線**：空方型態確認線 (M頭、頭肩頂)。

            #### 3. 📈 均線代表
            * 🟦 **藍線 5日** (週線) / 🟧 **橘線 20日** (月線) / 🟩 **綠線 60日** (季線)。

            #### 4. 🛡️ 關鍵支撐與壓力 (若無型態時顯示)
            * **短線 (20日)**：🔸 淺橘虛線 (壓力) / 🔹 淺藍虛線 (支撐)
            * **波段 (60日)**：🔴 深紅虛線 (壓力) / 🔵 深藍虛線 (支撐)
            """)
