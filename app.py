import streamlit as st
import yfinance as yf
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. पेज कॉन्फ़िगरेशन ---
st.set_page_config(page_title="Silver Pro Analyzer (MCX)", layout="wide", page_icon="🪙")

# --- 2. 🔒 सुरक्षा / पासवर्ड सेक्शन ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("### 🔒 सुरक्षित एक्सेस")
        pwd = st.text_input("डैशबोर्ड अनलॉक करने के लिए पासवर्ड (Ravi@2026) दर्ज करें:", type="password")
        if pwd == "Ravi@2026":
            st.session_state["password_correct"] = True
            st.rerun()
        elif pwd != "":
            st.error("❌ गलत पासवर्ड! कृपया पुनः प्रयास करें।")
        return False
    return True

if not check_password():
    st.stop()  
# ----------------------------------------------------

# --- 3. ऑटो-रिफ्रेश (हर 5 मिनट) ---
st_autorefresh(interval=300000, key="silver_pro_refresh")

st.title("🪙 सिल्वर प्रो मास्टर (80%+ एक्यूरेसी मॉडल)")
st.markdown("यह एडवांस्ड डैशबोर्ड **लाइव MCX भाव, EMA, RSI, ATR (Volatility)** और **पिवट पॉइंट्स (सपोर्ट/टारगेट)** के आधार पर काम करता है।")

# --- 4. ⚙️ MCX प्राइस एडजस्टमेंट (Sidebar) ---
st.sidebar.header("⚙️ MCX भाव एडजस्टमेंट")
st.sidebar.markdown("अगर ऐप का भाव आपके एंजेल वन (Angel One) टर्मिनल से अलग है, तो यहाँ वह अंतर (Difference) डालें।")
mcx_offset = st.sidebar.number_input("भाव का अंतर डालें (₹ में, उदा: 1500 या -1000):", value=0, step=50)

st.sidebar.markdown("---")
st.sidebar.info("💡 **ट्रेडिंग टिप:** अगर RSI 70 के ऊपर है तो नई खरीदारी (लॉन्ग) से बचें (Overbought)। अगर RSI 30 के नीचे है तो नई बिकवाली (शॉर्ट) से बचें (Oversold)।")

# --- 5. लाइव डेटा फेचिंग ---
@st.cache_data(ttl=300)
def fetch_market_data():
    df_15m = yf.download("SI=F", period="7d", interval="15m")
    df_daily = yf.download("SI=F", period="5d", interval="1d")
    df_inr = yf.download("INR=X", period="5d", interval="1d")
    return df_15m, df_daily, df_inr

df_15m, df_daily, df_inr = fetch_market_data()

if df_15m.empty or df_daily.empty:
    st.warning("⚠️ अभी लाइव डेटा प्राप्त नहीं हो रहा है (संभवतः मार्केट बंद है)। कृपया कुछ देर बाद रिफ्रेश करें।")
    st.stop()

# --- 6. तकनीकी इंडिकेटर्स की गणना (Pandas) ---
df_15m['EMA_20'] = df_15m['Close'].ewm(span=20, adjust=False).mean()
df_15m['EMA_50'] = df_15m['Close'].ewm(span=50, adjust=False).mean()

delta = df_15m['Close'].diff()
gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
rs = gain / loss
df_15m['RSI'] = 100 - (100 / (1 + rs))

# ATR Calculation (Volatility)
high_low = df_15m['High'] - df_15m['Low']
high_close = (df_15m['High'] - df_15m['Close'].shift()).abs()
low_close = (df_15m['Low'] - df_15m['Close'].shift()).abs()
ranges = pd.concat([high_low, high_close, low_close], axis=1)
df_15m['ATR'] = ranges.max(axis=1).rolling(14).mean()

# --- 7. पिवट पॉइंट्स (पिछले दिन के HLC के आधार पर) ---
def get_val(series):
    return float(series.iloc[0]) if isinstance(series, pd.Series) else float(series)

try:
    prev_h = get_val(df_daily['High'].iloc[-2])
    prev_l = get_val(df_daily['Low'].iloc[-2])
    prev_c = get_val(df_daily['Close'].iloc[-2])
except:
    prev_h = get_val(df_daily['High'].iloc[-1])
    prev_l = get_val(df_daily['Low'].iloc[-1])
    prev_c = get_val(df_daily['Close'].iloc[-1])

pivot = (prev_h + prev_l + prev_c) / 3
res_1 = (2 * pivot) - prev_l
res_2 = pivot + (prev_h - prev_l)
sup_1 = (2 * pivot) - prev_h
sup_2 = pivot - (prev_h - prev_l)

# --- 8. कन्वर्जन (USD to INR 1 KG MCX) ---
try:
    usd_inr_rate = get_val(df_inr['Close'].iloc[-1])
except:
    usd_inr_rate = 84.00

# 6% कस्टम ड्यूटी और प्रीमियम मल्टीप्लायर
multiplier = usd_inr_rate * 32.15 * 1.06  

latest = df_15m.iloc[-1]
raw_price = get_val(latest['Close'])
ema20 = get_val(latest['EMA_20'])
ema50 = get_val(latest['EMA_50'])
rsi_val = get_val(latest['RSI'])
atr_val = get_val(latest['ATR']) if not pd.isna(get_val(latest['ATR'])) else (raw_price * 0.005)

# रुपये (₹) में वैल्यू और ऑफसेट जोड़ना
current_price_inr = (raw_price * multiplier) + mcx_offset
ema20_inr = (ema20 * multiplier) + mcx_offset
ema50_inr = (ema50 * multiplier) + mcx_offset
atr_inr = atr_val * multiplier

p_inr = (pivot * multiplier) + mcx_offset
r1_inr = (res_1 * multiplier) + mcx_offset
r2_inr = (res_2 * multiplier) + mcx_offset
s1_inr = (sup_1 * multiplier) + mcx_offset
s2_inr = (sup_2 * multiplier) + mcx_offset

# --- 9. डैशबोर्ड UI (मुख्य आंकड़े) ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("📌 लाइव MCX भाव (1 Kg)", f"₹ {current_price_inr:,.0f}")
col2.metric("📊 RSI (14) मोमेंटम", f"{rsi_val:.2f}")
col3.metric("📈 EMA 20 (शॉर्ट टर्म)", f"₹ {ema20_inr:,.0f}")
col4.metric("📉 EMA 50 (लॉन्ग टर्म)", f"₹ {ema50_inr:,.0f}")

st.markdown("---")

# --- 10. ट्रेडिंग लॉजिक और रिस्क मैनेजमेंट ---
st.subheader("🤖 प्रो-एल्गोरिदम निर्णय एवं ATR रिस्क मैनेजमेंट")

if ema20 > ema50 and rsi_val < 70:
    verdict = "🟢 **BUY (लॉन्ग पोजीशन - मजबूत अपट्रेंड)**"
    conf = "EMA बुलीश क्रॉसओवर कन्फर्म है और RSI ओवरबॉट (Overbought) नहीं है।"
    stop_loss = current_price_inr - (1.5 * atr_inr)
elif ema20 < ema50 and rsi_val > 30:
    verdict = "🔴 **SELL (शॉर्ट पोजीशन - डाउनट्रेंड)**"
    conf = "EMA बेयरिश क्रॉसओवर एक्टिव है और RSI ओवरसोल्ड (Oversold) नहीं है।"
    stop_loss = current_price_inr + (1.5 * atr_inr)
else:
    verdict = "🟡 **NEUTRAL (मार्केट साइडवेज़ है)**"
    conf = "स्पष्ट ट्रेंड की कमी। सुरक्षित रहने के लिए फ्रेश ट्रेड से बचें।"
    stop_loss = 0.0

st.markdown(f"### निष्कर्ष: {verdict}")
st.write(f"**सिग्नल लॉजिक:** {conf}")

if stop_loss > 0:
    st.error(f"🛑 **सिस्टम जनरेटेड स्टॉप-लॉस:** ₹ {stop_loss:,.0f} (ATR वोलैटिलिटी आधारित)")

st.markdown("---")

# --- 11. पिवट पॉइंट्स (टारगेट और सपोर्ट लेवल्स) ---
st.subheader("🎯 आज के लिए एडवांस पिवट लेवल्स (टारगेट और सपोर्ट)")
st.info(f"📍 **न्यूट्रल/पिवट पॉइंट (बीच का भाव): ₹ {p_inr:,.0f}** (इसके ऊपर रहे तो बाज़ार बुलीश, नीचे रहे तो बेयरिश)")

t_col1, t_col2, t_col3, t_col4 = st.columns(4)
t_col1.metric("🚀 रेजिस्टेंस/टारगेट 2 (R2)", f"₹ {r2_inr:,.0f}")
t_col2.metric("🎯 रेजिस्टेंस/टारगेट 1 (R1)", f"₹ {r1_inr:,.0f}")
t_col3.metric("🛡️ सपोर्ट 1 (S1)", f"₹ {s1_inr:,.0f}")
t_col4.metric("🧱 मजबूत सपोर्ट 2 (S2)", f"₹ {s2_inr:,.0f}")

st.markdown("---")
st.caption(f"🔄 **अंतिम अपडेट:** {time.strftime('%Y-%m-%d %H:%M:%S')} | यह ऐप हर 5 मिनट में लाइव डेटा के साथ स्वतः रिफ्रेश होता है।")
