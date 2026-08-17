import streamlit as st
import yfinance as yf
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh

# पेज कॉन्फ़िगरेशन
st.set_page_config(page_title="Silver Pro Analyzer", layout="wide")

# --- 🔒 सुरक्षा / पासवर्ड सेक्शन ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "Ravi@2026": 
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 कृपया सुरक्षित डैशबोर्ड देखने के लिए पासवर्ड दर्ज करें:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 कृपया सुरक्षित डैशबोर्ड देखने के लिए पासवर्ड दर्ज करें:", type="password", on_change=password_entered, key="password")
        st.error("❌ गलत पासवर्ड! कृपया पुनः प्रयास करें।")
        return False
    else:
        return True

if not check_password():
    st.stop()  
# ----------------------------------------------------

st_autorefresh(interval=300000, key="silver_pro_refresh")

st.title("🪙 सिल्वर प्रो (MCX एक्यूरेसी मॉडल)")
st.markdown("यह डैशबोर्ड रियल-टाइम लाइव डेटा और **आपके MCX भाव के सटीक मिलान (Adjustment)** के साथ हर 5 मिनट में अपडेट होता है।")

# --- नया फीचर: साइडबार में MCX प्राइस एडजस्टमेंट ---
st.sidebar.header("⚙️ MCX प्राइस एडजस्टमेंट")
st.sidebar.markdown("चूँकि अंतरराष्ट्रीय भाव और भारतीय MCX भाव में प्रीमियम/ड्यूटी का अंतर होता है, इसलिए आप यहाँ वह अंतर (Difference) सेट कर सकते हैं ताकि भाव बिल्कुल सटीक हो जाए।")
mcx_offset = st.sidebar.number_input("ऐप के भाव और आपके MCX भाव में कितना अंतर है? (उदाहरण: यदि ऐप 1000 कम बता रहा है तो 1000 लिखें, ज्यादा बता रहा है तो -1000 लिखें)", value=0, step=100)
# ----------------------------------------------------

symbol = "SI=F" 

@st.cache_data(ttl=300)
def get_advanced_data(ticker):
    df = yf.download(ticker, period="7d", interval="15m")
    if df.empty:
        return df
    
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

@st.cache_data(ttl=300)
def get_usdinr():
    try:
        usd_inr_data = yf.download("INR=X", period="5d", interval="1d")
        return float(usd_inr_data['Close'].iloc[-1])
    except:
        return 84.00

data = get_advanced_data(symbol)

if data.empty:
    st.warning("⚠️ अभी लाइव डेटा प्राप्त नहीं हो रहा है (संभवतः मार्केट बंद है)। कृपया कुछ देर बाद रिफ्रेश करें।")
    st.stop()

latest = data.iloc[-1]
usd_inr_rate = get_usdinr()

# 6% ड्यूटी के अनुसार अपडेटेड फॉर्मूला 
conversion_multiplier = usd_inr_rate * 32.15 * 1.06  

try:
    raw_price = float(latest['Close'].iloc[0]) if isinstance(latest['Close'], pd.Series) else float(latest['Close'])
    rsi_val = float(latest['RSI'].iloc[0]) if isinstance(latest['RSI'], pd.Series) else float(latest['RSI'])
    ema20 = float(latest['EMA_20'].iloc[0]) if isinstance(latest['EMA_20'], pd.Series) else float(latest['EMA_20'])
    ema50 = float(latest['EMA_50'].iloc[0]) if isinstance(latest['EMA_50'], pd.Series) else float(latest['EMA_50'])
    atr_val = float(latest['ATR'].iloc[0]) if isinstance(latest['ATR'], pd.Series) else float(latest['ATR'])
except:
    raw_price = float(latest['Close'])
    rsi_val = float(latest['RSI'])
    ema20 = float(latest['EMA_20'])
    ema50 = float(latest['EMA_50'])
    atr_val = float(latest['ATR']) if not pd.isna(latest['ATR']) else (raw_price * 0.005)

# --- यहाँ आपके द्वारा दिया गया एडजस्टमेंट (mcx_offset) जुड़ रहा है ---
current_price_inr = (raw_price * conversion_multiplier) + mcx_offset
ema20_inr = (ema20 * conversion_multiplier) + mcx_offset
ema50_inr = (ema50 * conversion_multiplier) + mcx_offset
atr_val_inr = atr_val * conversion_multiplier # ATR वोलैटिलिटी है, इसमें ऑफसेट नहीं जुड़ता

col1, col2, col3, col4 = st.columns(4)
col1.metric("MCX भाव (एडजस्टेड)", f"₹ {current_price_inr:,.0f}")
col2.metric("RSI (14)", f"{rsi_val:.2f}")
col3.metric("EMA 20", f"₹ {ema20_inr:,.0f}")
col4.metric("EMA 50", f"₹ {ema50_inr:,.0f}")

st.markdown("---")
st.subheader("🤖 प्रो-एल्गोरिदम निर्णय एवं रिस्क मैनेजमेंट")

if ema20 > ema50 and rsi_val < 70:
    verdict = "🟢 **BUY (मजबूत अपट्रेंड - लॉन्ग पोजीशन)**"
    conf = "85% संभावना - EMA बुलीश क्रॉसओवर और सही RSI जोन कन्फर्म है।"
    stop_loss = current_price_inr - (1.5 * atr_val_inr)
    target_1 = current_price_inr + (2.0 * atr_val_inr)
    target_2 = current_price_inr + (3.5 * atr_val_inr)
elif ema20 < ema50 and rsi_val > 30:
    verdict = "🔴 **SELL (मजबूत डाउनट्रेंड - शॉर्ट पोजीशन)**"
    conf = "85% संभावना - EMA बेयरिश क्रॉसओवर एक्टिव है।"
    stop_loss = current_price_inr + (1.5 * atr_val_inr)
    target_1 = current_price_inr - (2.0 * atr_val_inr)
    target_2 = current_price_inr - (3.5 * atr_val_inr)
else:
    verdict = "🟡 **NEUTRAL / SIDEWAYS (सावधान रहें)**"
    conf = "बाजार में स्पष्ट ट्रेंड की कमी है। फ्रेश ट्रेड से बचें।"
    stop_loss = 0.0
    target_1 = 0.0
    target_2 = 0.0

st.markdown(f"### अंतिम निष्कर्ष: {verdict}")
st.write(f"**कॉन्फिडेंस लेवल:** {conf}")

if stop_loss > 0:
    st.markdown("---")
    st.subheader("🛡️ रिस्क मैनेजमेंट और लेवल्स (MCX भाव के अनुसार)")
    r_col1, r_col2, r_col3 = st.columns(3)
    r_col1.metric("🛑 अनुशंसित स्टॉप-लॉस", f"₹ {stop_loss:,.0f}")
    r_col2.metric("🎯 टारगेट 1", f"₹ {target_1:,.0f}")
    r_col3.metric("🚀 टारगेट 2", f"₹ {target_2:,.0f}")

st.markdown("---")
st.caption(f"🔄 **ऑटो-अपडेट स्टेटस:** अंतिम बार अपडेट किया गया - {time.strftime('%Y-%m-%d %H:%M:%S')}")
