import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股型態獵人", layout="wide")
st.title("📈 AI 股票型態分析 App")
st.markdown("輸入代號，自動偵測 **箱型、W底、杯柄、三角收斂** 等型態。")

# --- 2. 側邊欄輸入 ---
with st.sidebar:
    st.header("設定")
    default_stocks = ["2330.TW", "2317.TW", "3231.TW", "3491.TWO", "2603.TW"]
    stock_id = st.text_input("輸入股票代號", value="2330.TW")
    st.caption("範例：2330.TW (上市) / 3491.TWO (上櫃)")
    
    st.markdown("---")
    st.markdown("**內建觀察清單：**")
    for s in default_stocks:
        if st.button(s):
            stock_id = s # 點擊後自動填入

    run_btn = st.button("開始分析", type="primary")

# --- 3. 核心邏輯 (包含所有型態偵測) ---
def get_data(symbol):
    try:
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df if len(df) > 120 else None
    except: return None

def check_patterns(df):
    signals = []
    
    # A. 箱型 (Box Breakout)
    box_high = df['High'].iloc[-61:-1].max()
    box_low = df['Low'].iloc[-61:-1].min()
    amp = (box_high - box_low) / box_low
    if amp < 0.15 and df['Close'].iloc[-1] > box_high:
        signals.append({"name": "Box Breakout", "type": "box", "levels": [box_high, box_low], "colors": ['blue', 'orange']})
    
    # B. W底 (Double Bottom)
    recent_low = df['Low'].iloc[-10:].min()
    prev_low = df['Low'].iloc[-60:-20].min()
    if 0.97 < (recent_low/prev_low) < 1.03 and df['Close'].iloc[-1] > recent_low*1.02:
        signals.append({"name": "Double Bottom", "type": "line", "levels": [recent_low], "colors": ['blue']})
    
    # C. 三角收斂 (Triangle Squeeze)
    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    bw = ((ma20+2*std20) - (ma20-2*std20))/ma20
    if bw.iloc[-1] < 0.05:
         signals.append({"name": "Triangle Squeeze", "type": "bollinger", "data": [ma20+2*std20, ma20-2*std20]})

    # D. 杯柄 (Cup & Handle)
    data = df.iloc[-120:]
    left_rim = data['High'].iloc[:40].max()
    bottom = data['Low'].iloc[40:100].min()
    right_rim = data['High'].iloc[100:].max()
    if (bottom < left_rim * 0.85) and (0.9 < right_rim/left_rim < 1.1):
        if df['Close'].iloc[-1] > right_rim * 0.9:
            signals.append({"name": "Cup & Handle", "type": "line", "levels": [left_rim], "colors": ['orange']})
            
    return signals

# --- 4. 主程式執行 ---
# 自動執行分析 (當按下按鈕或點選側邊欄股票時)
if run_btn or stock_id:
    with st.spinner(f"正在分析 {stock_id} ..."):
        df = get_data(stock_id)
        
        if df is None:
            st.error(f"❌ 找不到 {stock_id} 的資料，請檢查代號是否正確。")
        else:
            # 取得即時數據
            last_price = df['Close'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            change = last_price - df['Close'].iloc[-2]
            pct_change = (change / df['Close'].iloc[-2]) * 100
            
            # 顯示看板
            col1, col2, col3 = st.columns(3)
            col1.metric("收盤價", f"{last_price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            col2.metric("成交量", f"{int(last_vol/1000)} 張")
            col3.markdown(f"**資料日期**: {df.index[-1].date()}")
            
            # 偵測型態
            signals = check_patterns(df)
            
            # 設定台股配色 (紅漲綠跌)
            mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='inherit')
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
            
            # 準備畫圖
            ap = []
            h_lines = []
            h_colors = []
            title_text = f"{stock_id} Analysis"
            
            if signals:
                names = [s['name'] for s in signals]
                # 顯示中文結果
                st.success(f"🔥 發現訊號：{' + '.join(names)}")
                title_text = f"{stock_id} Pattern: {' + '.join(names)}"
                
                # 加入圖表標示
                for sig in signals:
                    if 'levels' in sig:
                        h_lines.extend(sig['levels'])
                        h_colors.extend(sig['colors'])
                    if sig['type'] == 'bollinger':
                        ap.append(mpf.make_addplot(sig['data'][0].iloc[-120:], color='gray', alpha=0.5))
                        ap.append(mpf.make_addplot(sig['data'][1].iloc[-120:], color='gray', alpha=0.5))
            else:
                st.info("👀 目前無特定型態，顯示標準 K 線圖。")

            # 繪製圖表
            fig, ax = mpf.plot(
                df.iloc[-120:], 
                type='candle', 
                style=s, 
                volume=True, 
                mav=(20,60),
                hlines=dict(hlines=h_lines, colors=h_colors, linestyle='-.') if h_lines else None,
                addplot=ap if ap else None,
                title=title_text,
                returnfig=True
            )
            st.pyplot(fig)
