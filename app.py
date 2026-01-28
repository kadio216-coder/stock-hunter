import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import twstock

# --- 1. 頁面設定 ---
st.set_page_config(page_title="股票型態分析", layout="wide")
st.title("📈 股票型態分析")
st.markdown("自動偵測型態，並標示 **短線(20日)** 與 **波段(60日)** 之支撐壓力區間。")

# --- 2. 側邊欄輸入 ---
with st.sidebar:
    st.header("設定")
    stock_id = st.text_input("輸入股票代號", value="2330.TW")
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

def check_patterns(df):
    """偵測各種技術型態"""
    signals = []
    today = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. 箱型 (Box Breakout)
    box_high = df['High'].iloc[-61:-1].max()
    box_low = df['Low'].iloc[-61:-1].min()
    amp = (box_high - box_low) / box_low
    if amp < 0.15 and today['Close'] > box_high:
        signals.append({"name": "Box Breakout", "type": "box", "levels": [box_high, box_low], "colors": ['blue', 'orange']})
    
    # 2. W底 (Double Bottom)
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

    # 4. 頭肩底
    data_hs = df.iloc[-60:]
    p1 = data_hs['Low'].iloc[0:20].min()
    p2 = data_hs['Low'].iloc[20:40].min()
    p3 = data_hs['Low'].iloc[40:].min()
    if (p2 < p1) and (p2 < p3) and (0.9 < p1/p3 < 1.1):
        signals.append({"name": "Head & Shoulders", "type": "line", "levels": [p2], "colors": ['blue']})

    # 5. 三角收斂
    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    bw = ((ma20+2*std20) - (ma20-2*std20))/ma20
    if bw.iloc[-1] < 0.05:
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

    # K線訊號
    is_engulfing = (prev['Close'] < prev['Open']) and (today['Close'] > today['Open']) and (today['Close'] > prev['Open']) and (today['Open'] < prev['Close'])
    if is_engulfing: signals.append({"name": "Bullish Engulfing", "type": "text"})

    body = abs(today['Close'] - today['Open'])
    lower_shadow = min(today['Close'], today['Open']) - today['Low']
    is_hammer = (lower_shadow > body * 2) and (today['Close'] > prev['Close'])
    if is_hammer: signals.append({"name": "Hammer", "type": "text"})

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
            
            # 設定台股配色 (紅漲綠跌)
            mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='inherit')
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
            
            ap = []
            h_lines = []
            h_colors = []
            title_text = f"{stock_id} Analysis"
            
            # 中文名稱對照表
            name_map = {
                "Box Breakout": "箱型突破", "Double Bottom": "W底", "Double Top (Sell)": "M頭(賣訊)",
                "Head & Shoulders": "頭肩底", "Triangle Squeeze": "三角收斂", "Cup & Handle": "杯柄型態",
                "Rounding Bottom": "圓弧底", "Bullish Engulfing": "長紅吞噬", "Hammer": "錘頭線"
            }

            if signals:
                display_names = [name_map.get(s['name'], s['name']) for s in signals]
                if "Double Top (Sell)" in [s['name'] for s in signals]:
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

            # --- 自動畫支撐/壓力線邏輯 (格式更新版) ---
            if show_sr or not h_lines:
                # 1. 計算數值
                short_high = df['High'].iloc[-20:].max()
                short_low = df['Low'].iloc[-20:].min()
                medium_high = df['High'].iloc[-60:].max()
                medium_low = df['Low'].iloc[-60:].min()
                
                # 2. 決定是否畫線 (視覺化邏輯不變，避免線條重疊)
                if abs(short_high - medium_high) / medium_high > 0.02:
                    h_lines.append(short_high)
                    h_colors.append('orange') # 淺橘: 短壓
                h_lines.append(medium_high)
                h_colors.append('red') # 深紅: 長壓
                
                if abs(short_low - medium_low) / medium_low > 0.02:
                    h_lines.append(short_low)
                    h_colors.append('skyblue') # 淺藍: 短撐
                h_lines.append(medium_low)
                h_colors.append('blue') # 深藍: 長撐
                
                # 3. 顯示文字 (依照指定格式更新)
                st.caption(f"🔹 **短線 (20日)**：{short_high:.2f} (壓力) / {short_low:.2f} (支撐)")
                st.caption(f"📊 **波段 (60日)**：{medium_high:.2f} (壓力) / {medium_low:.2f} (支撐)")

            # --- 繪圖區 ---
            plot_args = dict(
                type='candle', 
                style=s, 
                volume=True, 
                mav=(5, 20, 60), 
                title=title_text, 
                returnfig=True
            )
            
            if h_lines: 
                plot_args['hlines'] = dict(hlines=h_lines, colors=h_colors, linestyle='-.', linewidths=1.0)
            if ap: 
                plot_args['addplot'] = ap

            fig, ax = mpf.plot(df.iloc[-120:], **plot_args)
            st.pyplot(fig)
            
            # --- 底部說明區 ---
            st.markdown("---")
            st.markdown("""
            ### 📝 圖表判讀說明
            1. **型態偵測**：自動掃描 9 種經典技術型態 (含買賣訊號)。
            2. **均線代表**：🟦 **藍線 5日** (週線) / 🟧 **橘線 20日** (月線) / 🟩 **綠線 60日** (季線)。
            3. **關鍵區間**：
                * **短線 (20日)**：🔸 淺橘虛線 (壓力) / 🔹 淺藍虛線 (支撐)
                * **波段 (60日)**：🔴 深紅虛線 (壓力) / 🔵 深藍虛線 (支撐)
            """)
