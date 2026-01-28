import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import twstock  # <--- 新增這個套件

# --- 1. 頁面設定 ---
st.set_page_config(page_title="股票型態分析", layout="wide")
st.title("📈 股票型態分析")
st.markdown("輸入代號，自動偵測 **箱型、W底、頭肩底、杯柄、三角收斂、K線轉折** 等型態。")

# --- 2. 側邊欄輸入 ---
with st.sidebar:
    st.header("設定")
    stock_id = st.text_input("輸入股票代號", value="2330.TW")
    st.caption("範例：2330.TW (上市) / 3491.TWO (上櫃)")
    
    run_btn = st.button("開始分析", type="primary")

# --- 3. 核心邏輯 ---

# 新增：取得股票中文名稱
def get_stock_name(symbol):
    try:
        # 只處理台股代號 (去除 .TW 或 .TWO)
        code = symbol.split('.')[0]
        # 使用 twstock 查詢
        if code in twstock.codes:
            return twstock.codes[code].name
    except:
        pass
    return symbol # 如果找不到 (例如美股)，就回傳原本代號

def get_data(symbol):
    try:
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df if len(df) > 120 else None
    except: return None

def check_patterns(df):
    signals = []
    today = df.iloc[-1]
    prev = df.iloc[-2]
    
    # A. 箱型
    box_high = df['High'].iloc[-61:-1].max()
    box_low = df['Low'].iloc[-61:-1].min()
    amp = (box_high - box_low) / box_low
    if amp < 0.15 and today['Close'] > box_high:
        signals.append({"name": "Box Breakout", "type": "box", "levels": [box_high, box_low], "colors": ['blue', 'orange']})
    
    # B. W底
    recent_low = df['Low'].iloc[-10:].min()
    prev_low = df['Low'].iloc[-60:-20].min()
    if 0.97 < (recent_low/prev_low) < 1.03 and today['Close'] > recent_low*1.02:
        signals.append({"name": "Double Bottom", "type": "line", "levels": [recent_low], "colors": ['blue']})
    
    # C. 頭肩底
    data_hs = df.iloc[-60:]
    p1 = data_hs['Low'].iloc[0:20].min()
    p2 = data_hs['Low'].iloc[20:40].min()
    p3 = data_hs['Low'].iloc[40:].min()
    if (p2 < p1) and (p2 < p3) and (0.9 < p1/p3 < 1.1):
        signals.append({"name": "Head & Shoulders", "type": "line", "levels": [p2], "colors": ['blue']})

    # D. 三角收斂
    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    bw = ((ma20+2*std20) - (ma20-2*std20))/ma20
    if bw.iloc[-1] < 0.05:
         signals.append({"name": "Triangle Squeeze", "type": "bollinger", "data": [ma20+2*std20, ma20-2*std20]})

    # E. 杯柄
    data_ch = df.iloc[-120:]
    left_rim = data_ch['High'].iloc[:40].max()
    bottom = data_ch['Low'].iloc[40:100].min()
    right_rim = data_ch['High'].iloc[100:].max()
    if (bottom < left_rim * 0.85) and (0.9 < right_rim/left_rim < 1.1):
        if today['Close'] > right_rim * 0.9:
            signals.append({"name": "Cup & Handle", "type": "line", "levels": [left_rim], "colors": ['orange']})

    # F. 長紅吞噬
    is_engulfing = (prev['Close'] < prev['Open']) and \
                   (today['Close'] > today['Open']) and \
                   (today['Close'] > prev['Open']) and \
                   (today['Open'] < prev['Close'])
    if is_engulfing:
        signals.append({"name": "Bullish Engulfing", "type": "text"})

    # G. 錘頭線
    body = abs(today['Close'] - today['Open'])
    lower_shadow = min(today['Close'], today['Open']) - today['Low']
    is_hammer = (lower_shadow > body * 2) and (today['Close'] > prev['Close'])
    if is_hammer:
        signals.append({"name": "Hammer", "type": "text"})

    return signals

# --- 4. 主程式執行 ---
if run_btn or stock_id:
    with st.spinner(f"正在分析 {stock_id} ..."):
        df = get_data(stock_id)
        
        if df is None:
            st.error(f"❌ 找不到 {stock_id} 的資料，請檢查代號是否正確。")
        else:
            # 取得中文名稱
            stock_name = get_stock_name(stock_id)
            
            last_price = df['Close'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            change = last_price - df['Close'].iloc[-2]
            pct_change = (change / df['Close'].iloc[-2]) * 100
            
            # 顯示大標題：名稱 (代號)
            st.subheader(f"{stock_name} ({stock_id})")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("收盤價", f"{last_price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            col2.metric("成交量", f"{int(last_vol/1000)} 張")
            col3.markdown(f"**資料日期**: {df.index[-1].date()}")
            
            signals = check_patterns(df)
            
            mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='inherit')
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
            
            ap = []
            h_lines = []
            h_colors = []
            title_text = f"{stock_name} ({stock_id}) Analysis" # 圖表標題也加上中文名
            
            name_map = {
                "Box Breakout": "箱型突破",
                "Double Bottom": "W底",
                "Head & Shoulders": "頭肩底",
                "Triangle Squeeze": "三角收斂",
                "Cup & Handle": "杯柄型態",
                "Bullish Engulfing": "長紅吞噬",
                "Hammer": "錘頭線"
            }

            if signals:
                display_names = [name_map.get(s['name'], s['name']) for s in signals]
                st.success(f"🔥 發現訊號：{' + '.join(display_names)}")
                
                eng_names = [s['name'] for s in signals]
                # 圖表標題改用 代號 + 英文型態 (避免亂碼)
                title_text = f"{stock_id} Pattern: {' + '.join(eng_names)}"
                
                for sig in signals:
                    if 'levels' in sig:
                        h_lines.extend(sig['levels'])
                        h_colors.extend(sig['colors'])
                    if sig.get('type') == 'bollinger':
                        ap.append(mpf.make_addplot(sig['data'][0].iloc[-120:], color='gray', alpha=0.5))
                        ap.append(mpf.make_addplot(sig['data'][1].iloc[-120:], color='gray', alpha=0.5))
            else:
                st.info("👀 目前無特定型態，顯示標準 K 線圖。")

            plot_args = dict(
                type='candle', 
                style=s, 
                volume=True, 
                mav=(20,60),
                title=title_text,
                returnfig=True
            )
            
            if h_lines:
                plot_args['hlines'] = dict(hlines=h_lines, colors=h_colors, linestyle='-.')
            
            if ap:
                plot_args['addplot'] = ap

            fig, ax = mpf.plot(df.iloc[-120:], **plot_args)
            st.pyplot(fig)
