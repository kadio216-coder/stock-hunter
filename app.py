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
    stock_id = st.text_input("輸入股票代號", value="3060.TW") 
    st.caption("範例：2330.TW (上市) / 3491.TWO (上櫃)")
    
    # 功能開關
    show_sr = st.checkbox("顯示預設支撐/壓力 (色塊)", value=True)
    
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
        # 強制四捨五入，修復小數點誤差
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
    """偵測各種技術型態 (高靈敏度版)"""
    signals = []
    df_kd = calculate_kd(df)
    today = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. KD 鈍化
    last_3_k = df_kd['K'].iloc[-3:]
    if (last_3_k > 80).all():
        signals.append({"name": "KD High Passivation", "type": "text"})
    elif (last_3_k < 20).all():
        signals.append({"name": "KD Low Passivation", "type": "text"})

    # 2. 箱型整理
    period_high = df['High'].iloc[-60:-1].max()
    period_low = df['Low'].iloc[-60:-1].min()
    amp = (period_high - period_low) / period_low
    
    if amp < 0.50:
        if today['Close'] > period_high:
            signals.append({"name": "Box Breakout", "type": "box", "levels": [period_high, period_low], "colors": ['red', 'green']})
        elif period_low < today['Close'] < period_high:
            if today['Close'] > (period_low + period_high)/2:
                # 這裡顏色改用 'orange' 代表箱型區域
                signals.append({"name": "Box Consolidation", "type": "box", "levels": [period_high, period_low], "colors": ['orange']})
    
    # 3. W底
    recent_low = df['Low'].iloc[-10:].min()
    prev_low = df['Low'].iloc[-60:-20].min()
    if 0.90 < (recent_low/prev_low) < 1.10 and today['Close'] > recent_low*1.05:
        signals.append({"name": "Double Bottom", "type": "line", "levels": [recent_low], "colors": ['blue']})

    # 4. M頭
    recent_high = df['High'].iloc[-10:].max()
    prev_high = df['High'].iloc[-60:-20].max()
    if 0.90 < (recent_high/prev_high) < 1.10:
        if today['Close'] < df['Low'].iloc[-20:].min():
             signals.append({"name": "Double Top (Sell)", "type": "line", "levels": [recent_high], "colors": ['green']})

    # 5. 頭肩底/頂
    data_hs = df.iloc[-60:]
    p1 = data_hs['Low'].iloc[0:20].min()
    p2 = data_hs['Low'].iloc[20:40].min() 
    p3 = data_hs['Low'].iloc[40:].min()
    if (p2 < p1) and (p2 < p3): 
        signals.append({"name": "Head & Shoulders Bottom", "type": "line", "levels": [p2], "colors": ['blue']})

    p1_h = data_hs['High'].iloc[0:20].max()
    p2_h = data_hs['High'].iloc[20:40].max() 
    p3_h = data_hs['High'].iloc[40:].max()
    if (p2_h > p1_h) and (p2_h > p3_h):
        neckline = data_hs['Low'].min()
        if today['Close'] < neckline:
             signals.append({"name": "Head & Shoulders Top", "type": "line", "levels": [p2_h], "colors": ['green']})

    # 6. 三角收斂
    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    bw = ((ma20+2*std20) - (ma20-2*std20))/ma20
    if bw.iloc[-5:].min() < 0.15:
         signals.append({"name": "Triangle Squeeze", "type": "bollinger", "data": [ma20+2*std20, ma20-2*std20]})

    # 7. K線型態
    is_engulfing = (prev['Close'] < prev['Open']) and (today['Close'] > today['Open']) and (today['Close'] > prev['Open']) and (today['Open'] < prev['Close'])
    if is_engulfing: 
        signals.append({"name": "Bullish Engulfing", "type": "line", "levels": [today['High']], "colors": ['red']})

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
            st.error(f"❌ 找不到 {stock_id} 的資料。")
        else:
            stock_name = get_stock_name(stock_id)
            
            # 成交量顏色 (精準券商版：漲紅跌綠，平盤看K棒)
            prev_close = df['Close'].shift(1).fillna(0)
            def get_vol_color(row):
                if row['Close'] > row['PrevClose']: return 'red'
                elif row['Close'] < row['PrevClose']: return 'green'
                else: return 'red' if row['Close'] >= row['Open'] else 'green'
            
            temp_df = pd.DataFrame({'Close': df['Close'], 'Open': df['Open'], 'PrevClose': prev_close})
            df['VolColor'] = temp_df.apply(get_vol_color, axis=1)

            plot_data = df.iloc[-120:]
            vol_colors = plot_data['VolColor'].tolist()

            # 數據看板
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
            
            title_text = f"{stock_id} Analysis"
            name_map = {
                "Box Breakout": "箱型突破", "Box Consolidation": "箱型整理中", "Double Bottom": "W底", 
                "Double Top (Sell)": "M頭(賣訊)", "Head & Shoulders Bottom": "頭肩底", 
                "Head & Shoulders Top": "頭肩頂(賣訊)", "Triangle Squeeze": "三角收斂", 
                "Bullish Engulfing": "長紅吞噬", "Hammer": "錘頭線",
                "KD High Passivation": "🔥 KD高檔鈍化", "KD Low Passivation": "⚠️ KD低檔鈍化"
            }

            # 準備色塊資料 (取代原本的 hlines)
            fill_zones = [] # 格式: (y_min, y_max, color)
            
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
                    # 處理色塊邏輯
                    if sig['type'] == 'box':
                        # 箱型：直接塗滿高低點之間
                        high = max(sig['levels'])
                        low = min(sig['levels'])
                        color = sig['colors'][0]
                        fill_zones.append((low, high, color))
                        
                    elif sig['type'] == 'line' and 'levels' in sig:
                        # 單線型態 (頸線/支撐)：畫成一個上下 1% 的寬帶
                        level = sig['levels'][0]
                        color = sig['colors'][0]
                        fill_zones.append((level * 0.99, level * 1.01, color))

                    # 布林通道維持原樣
                    if sig.get('type') == 'bollinger':
                        ap.append(mpf.make_addplot(sig['data'][0].iloc[-120:], color='gray', alpha=0.5))
                        ap.append(mpf.make_addplot(sig['data'][1].iloc[-120:], color='gray', alpha=0.5))
            else:
                st.info("👀 目前無特定型態 (顯示預設支撐壓力色塊)。")

            # 計算預設支撐/壓力 (轉換為色塊)
            if show_sr:
                short_high = df['High'].iloc[-20:].max()
                short_low = df['Low'].iloc[-20:].min()
                medium_high = df['High'].iloc[-60:].max()
                medium_low = df['Low'].iloc[-60:].min()
                
                # 波段(60日)的色塊常駐
                fill_zones.append((medium_high * 0.995, medium_high * 1.005, 'red')) # 波段壓
                fill_zones.append((medium_low * 0.995, medium_low * 1.005, 'blue'))  # 波段撐
                
                # 如果沒有偵測到更強的型態，再畫短線色塊
                if not signals:
                    fill_zones.append((short_high * 0.995, short_high * 1.005, 'orange'))
                    fill_zones.append((short_low * 0.995, short_low * 1.005, 'skyblue'))

            # --- 繪圖區 ---
            ap.append(mpf.make_addplot(plot_data['Volume'], type='bar', panel=1, color=vol_colors, ylabel='Volume'))

            plot_args = dict(
                type='candle', style=s, volume=False, mav=(5, 20, 60), 
                title=title_text, returnfig=True, panel_ratios=(3, 1)
            )
            
            if ap: 
                plot_args['addplot'] = ap

            # 使用 returnfig=True 拿到 figure 物件，手動畫色塊
            fig, axlist = mpf.plot(plot_data, **plot_args)
            ax_main = axlist[0] # 主圖表 axes

            # 畫出所有色塊 (Zones)
            for y1, y2, color in fill_zones:
                ax_main.axhspan(y1, y2, color=color, alpha=0.15) 

            st.pyplot(fig)

            # --- 說明區 (完全還原詳細版 + 修正視覺描述) ---
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
                    * **三角收斂**：計算布林通道 (20日均線標準差) 的壓縮程度 (近5日低於15%)。
            * ** 長期大底型態**
                * **偵測區間**：過去 120 個交易日 (約 6 個月 / 半年)
                * **包含型態**：
                    * **杯柄型態 (Cup & Handle)**：因為杯子需要時間打底，所以抓 120 天來確認左杯緣、杯底和右杯緣。
                    * **圓弧底 (Rounding Bottom)**：同樣需要長時間沉澱，所以比較 120 天內的頭尾與中間低點。

            #### 2. 🎨 圖表顏色意義 (色塊視覺化)
            為了讓支撐與壓力更直觀，圖表已將「線條」改為「背景色塊」顯示：
            * **🟦 藍色色塊**：**支撐區 (Support Zone)**。包含 W底頸線、箱型底部、波段低點。股價跌入此區容易有撐。
            * **🟥 紅色色塊**：**壓力區 (Resistance Zone)**。包含 M頭頸線、箱型頂部、波段高點。股價漲入此區容易遇壓。
            * **🟧 橘色色塊**：**箱型整理區 (Consolidation)**。當出現大面積橘色背景時，代表股價正在箱子裡震盪。
            * **🟩 綠色色塊**：**頭部型態 (Top Pattern)**。如頭肩頂、M頭的確認訊號。

            #### 3. 📈 均線代表
            * 🟦 **藍線 5日** (週線) / 🟧 **橘線 20日** (月線) / 🟩 **綠線 60日** (季線)。

            #### 4. 🛡️ 關鍵支撐與壓力 (若無型態時顯示)
            * **短線 (20日)**：顯示淺橘色塊 (壓力) / 淺藍色塊 (支撐)
            * **波段 (60日)**：顯示淡紅色塊 (壓力) / 淡藍色塊 (支撐)
            """)
