import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import feedparser
from urllib.parse import quote

st.set_page_config(
    page_title="文星AI交易系统 Pro",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
.main {
    background-color: #0E1117;
}
div[data-testid="stMetric"] {
    background: #1E222D;
    border-radius: 15px;
    padding: 15px;
    border: 1px solid #333;
}
.stAlert {
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

COMMON_STOCKS = {
    "SK海力士": {"ticker": "000660.KS", "ko": "SK하이닉스", "en": "SK hynix"},
    "三星电子": {"ticker": "005930.KS", "ko": "삼성전자", "en": "Samsung Electronics"},
    "三星电机": {"ticker": "009150.KS", "ko": "삼성전기", "en": "Samsung Electro-Mechanics"},
    "现代汽车": {"ticker": "005380.KS", "ko": "현대차", "en": "Hyundai Motor"},
    "斗山能源": {"ticker": "034020.KS", "ko": "두산에너빌리티", "en": "Doosan Enerbility"},
    "LS ELECTRIC": {"ticker": "010120.KS", "ko": "LS ELECTRIC", "en": "LS Electric"},
    "대한전선": {"ticker": "001440.KS", "ko": "대한전선", "en": "Taihan Cable"},
}

EN_POSITIVE_WORDS = [
    "rise", "rally", "surge", "jump", "gain", "strong", "growth", "record",
    "upgrade", "target raised", "buy rating", "outperform", "order", "contract",
    "supply", "demand", "AI", "HBM", "DRAM", "Nvidia", "Micron", "profit",
    "revenue", "boom"
]

EN_NEGATIVE_WORDS = [
    "fall", "drop", "decline", "slump", "selloff", "weak", "loss", "miss",
    "downgrade", "strike", "lawsuit", "delay", "risk", "concern", "tariff",
    "ban", "slowdown", "pressure", "warning"
]

KO_POSITIVE_WORDS = [
    "상승", "급등", "강세", "반등", "호실적", "실적 개선", "목표가 상향",
    "목표주가 상향", "매수", "수주", "공급계약", "계약", "대규모",
    "증가", "성장", "흑자", "수혜", "AI", "HBM", "반도체", "서버",
    "전력기기", "MLCC", "FCBGA", "실리콘캐패시터", "엔비디아", "마이크론",
    "메모리", "D램", "가격 상승", "투자 확대"
]

KO_NEGATIVE_WORDS = [
    "하락", "급락", "약세", "조정", "부진", "적자", "감소", "둔화",
    "목표가 하향", "목표주가 하향", "매도", "차익실현", "매물", "우려",
    "리스크", "위험", "파업", "소송", "지연", "취소", "경고", "규제",
    "관세", "수출 제한", "제재", "불확실성", "쇼크", "악재"
]

st.title("📈 文星AI交易系统 Pro")
st.caption("V3.0 Lite｜技术指标｜成交量｜韩文新闻｜英文新闻｜手动新闻｜风险雷达｜仓位管理")
st.warning("本系统仅供参考，不构成投资建议。股市有风险，操作需谨慎。")


def safe_float(value):
    if isinstance(value, pd.Series):
        return float(value.iloc[0])
    if isinstance(value, np.ndarray):
        return float(value.flatten()[0])
    return float(value)


def normalize_korean_ticker(code):
    code = code.strip().replace(" ", "")
    if code.endswith(".KS") or code.endswith(".KQ"):
        return code
    if not code.isdigit() or len(code) != 6:
        return None
    return f"{code}.KS"


def get_stock_data(ticker):
    df = yf.download(
        ticker,
        period="6mo",
        interval="1d",
        auto_adjust=False,
        progress=False
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df.dropna()


def add_indicators(df):
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss

    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()

    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    df["RETURN"] = df["Close"].pct_change()
    df["VOLATILITY"] = df["RETURN"].rolling(20).std()
    df["VOLUME_MA20"] = df["Volume"].rolling(20).mean()

    return df.dropna()


def score_text(text):
    text_lower = text.lower()
    positive_hits = []
    negative_hits = []

    for word in EN_POSITIVE_WORDS:
        if word.lower() in text_lower:
            positive_hits.append(word)

    for word in EN_NEGATIVE_WORDS:
        if word.lower() in text_lower:
            negative_hits.append(word)

    for word in KO_POSITIVE_WORDS:
        if word in text:
            positive_hits.append(word)

    for word in KO_NEGATIVE_WORDS:
        if word in text:
            negative_hits.append(word)

    score = len(positive_hits) * 3 - len(negative_hits) * 4
    score = max(-25, min(25, score))

    return score, list(set(positive_hits))[:10], list(set(negative_hits))[:10]


def get_google_news(query, language="ko"):
    titles = []

    try:
        encoded = quote(query)

        if language == "ko":
            url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        else:
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

        feed = feedparser.parse(url)

        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            if title:
                titles.append(title)

    except Exception:
        pass

    return titles


def get_yfinance_news(ticker):
    titles = []

    try:
        news = yf.Ticker(ticker).news
        for item in news[:10]:
            title = item.get("title", "")
            if title:
                titles.append(title)
    except Exception:
        pass

    return titles


def technical_score(df):
    latest = df.iloc[-1]

    close = safe_float(latest["Close"])
    ma5 = safe_float(latest["MA5"])
    ma20 = safe_float(latest["MA20"])
    rsi = safe_float(latest["RSI"])
    macd = safe_float(latest["MACD"])
    signal = safe_float(latest["MACD_SIGNAL"])

    score = 50
    reasons_good = []
    reasons_risk = []

    if close > ma5:
        score += 8
        reasons_good.append("股价站上5日线")
    else:
        score -= 8
        reasons_risk.append("股价跌破5日线")

    if close > ma20:
        score += 12
        reasons_good.append("股价站上20日线")
    else:
        score -= 12
        reasons_risk.append("股价跌破20日线")

    if ma5 > ma20:
        score += 8
        reasons_good.append("短线均线强于中线")
    else:
        score -= 8
        reasons_risk.append("短线均线走弱")

    if macd > signal:
        score += 8
        reasons_good.append("MACD动能偏强")
    else:
        score -= 8
        reasons_risk.append("MACD动能偏弱")

    if rsi >= 75:
        score -= 12
        reasons_risk.append("RSI过热，追高风险上升")
    elif rsi <= 30:
        score += 8
        reasons_good.append("RSI偏低，有反弹机会")

    return max(0, min(100, score)), reasons_good, reasons_risk


def volume_score(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = safe_float(latest["Close"])
    prev_close = safe_float(prev["Close"])
    volume = safe_float(latest["Volume"])
    volume_ma20 = safe_float(latest["VOLUME_MA20"])

    if volume_ma20 <= 0:
        return 0, "成交量数据不足", [], []

    change = (close - prev_close) / prev_close * 100
    ratio = volume / volume_ma20

    good = []
    risk = []
    score = 0

    if change > 1 and ratio >= 1.5:
        score = 12
        good.append("放量上涨，资金参与度高")
    elif change > 0 and ratio >= 1.2:
        score = 8
        good.append("温和放量上涨")
    elif change > 0 and ratio < 0.8:
        score = -5
        risk.append("上涨缩量，警惕冲高回落")
    elif change < -1 and ratio >= 1.5:
        score = -12
        risk.append("放量下跌，抛压较大")
    elif change < 0 and ratio >= 1.2:
        score = -8
        risk.append("下跌放量，资金面偏弱")
    elif change < 0 and ratio < 0.8:
        score = 3
        good.append("缩量下跌，恐慌不明显")
    else:
        score = 0

    return score, f"{ratio:.2f}倍", good, risk


def final_prediction(df, news_score, manual_score):
    latest = df.iloc[-1]

    close = safe_float(latest["Close"])
    volatility = safe_float(latest["VOLATILITY"])

    tech, good_t, risk_t = technical_score(df)
    vol_score, vol_ratio, good_v, risk_v = volume_score(df)

    final_score = tech + vol_score + news_score + manual_score
    final_score = max(0, min(100, final_score))

    expected_change_today = (final_score - 50) / 1200
    expected_change_next = (final_score - 50) / 1000

    today_mid = close * (1 + expected_change_today)
    next_mid = close * (1 + expected_change_next)

    price_range = max(volatility * 2, 0.025)

    result = {
        "close": round(close),
        "tech_score": round(tech),
        "volume_score": round(vol_score),
        "news_score": round(news_score),
        "manual_score": round(manual_score),
        "final_score": round(final_score),
        "today_mid": round(today_mid),
        "today_low": round(today_mid * (1 - price_range)),
        "today_high": round(today_mid * (1 + price_range)),
        "next_mid": round(next_mid),
        "next_low": round(next_mid * (1 - price_range)),
        "next_high": round(next_mid * (1 + price_range)),
        "rsi": round(safe_float(latest["RSI"]), 2),
        "ma5": round(safe_float(latest["MA5"])),
        "ma20": round(safe_float(latest["MA20"])),
        "vol_ratio": vol_ratio,
        "good_sources": good_t + good_v,
        "risk_sources": risk_t + risk_v,
    }

    return result


def risk_level(score):
    if score >= 80:
        return "A级（较低风险）"
    elif score >= 65:
        return "B级（中等风险）"
    elif score >= 50:
        return "C级（较高风险）"
    else:
        return "D级（高风险）"


def position_suggestion(score):
    if score >= 85:
        return "80%~90%"
    elif score >= 75:
        return "60%~70%"
    elif score >= 60:
        return "40%~50%"
    elif score >= 45:
        return "20%~30%"
    else:
        return "10%以下"


def trend_text(score):
    if score >= 80:
        return "🟢 强势偏多"
    elif score >= 65:
        return "🟡 偏多"
    elif score >= 50:
        return "⚪ 震荡"
    else:
        return "🔴 偏弱"


def ai_summary(score, risk_sources, good_sources):
    if score >= 80:
        base = "整体环境偏强，适合持有，但不要盲目追高。"
    elif score >= 65:
        base = "趋势偏多，可以继续观察，适合分批操作。"
    elif score >= 50:
        base = "当前偏震荡，建议控制仓位，等待方向明确。"
    else:
        base = "当前风险偏高，优先防守，不建议加仓。"

    if risk_sources:
        base += " 主要风险来自：" + "、".join(risk_sources[:3]) + "。"

    if good_sources:
        base += " 主要利好来自：" + "、".join(good_sources[:3]) + "。"

    return base


def holding_advice(current_price, cost_price, quantity, score):
    total_cost = cost_price * quantity
    total_value = current_price * quantity
    profit = total_value - total_cost
    rate = (current_price - cost_price) / cost_price * 100 if cost_price > 0 else 0

    stop_loss = current_price * 0.94
    take_profit_1 = current_price * 1.05
    take_profit_2 = current_price * 1.10

    if rate >= 15 and score < 65:
        advice = "盈利较大但评分转弱，建议分批止盈。"
        signal = "🔴 减仓/止盈"
    elif rate >= 10 and score >= 65:
        advice = "盈利不错且趋势仍强，建议持有并设置移动止盈。"
        signal = "🟡 持有"
    elif rate < -5 and score < 50:
        advice = "亏损且趋势偏弱，建议控制风险，跌破止损考虑减仓。"
        signal = "🔴 风险控制"
    elif score >= 75:
        advice = "综合趋势偏强，可持有观察，不建议追高满仓。"
        signal = "🟢 偏强"
    elif score >= 55:
        advice = "综合趋势中性偏多，适合持有观察。"
        signal = "🟡 观察"
    else:
        advice = "综合趋势偏弱，建议谨慎。"
        signal = "⚪ 谨慎"

    return {
        "profit": round(profit),
        "rate": round(rate, 2),
        "total_cost": round(total_cost),
        "total_value": round(total_value),
        "stop_loss": round(stop_loss),
        "take_profit_1": round(take_profit_1),
        "take_profit_2": round(take_profit_2),
        "signal": signal,
        "advice": advice,
    }


mode = st.radio("选择股票方式", ["常用股票", "输入韩股代码"], horizontal=True)

if mode == "常用股票":
    stock_name = st.selectbox("选择股票", list(COMMON_STOCKS.keys()))
    info = COMMON_STOCKS[stock_name]
    ticker = info["ticker"]
    ko_name = info["ko"]
    en_name = info["en"]
    display_name = stock_name
else:
    code = st.text_input("输入6位韩股代码，例如 000660、005930、009150", value="000660")
    ticker = normalize_korean_ticker(code)

    if ticker is None:
        st.error("请输入正确的6位韩股代码。")
        st.stop()

    custom_name = st.text_input("可选：输入公司韩文名/英文名，提高新闻搜索准确度", value="")
    ko_name = custom_name.strip() if custom_name.strip() else code
    en_name = custom_name.strip() if custom_name.strip() else code
    display_name = f"自定义股票 {ticker}"

quantity = st.number_input("持仓数量", min_value=0, value=1, step=1)
cost_price = st.number_input("你的成本价（韩元）", min_value=0, value=0, step=1000)

manual_news = st.text_area(
    "可选：手动粘贴新闻标题/内容，支持韩文、英文、中文",
    height=120,
    placeholder="例如：삼성전기, AI 서버용 실리콘캐패시터 대규모 공급 계약"
)

if st.button("开始分析"):
    with st.spinner("正在分析行情、新闻、成交量和风险来源..."):
        df = get_stock_data(ticker)

        if df is None or df.empty:
            st.error("行情数据获取失败，请检查代码或稍后再试。")
            st.stop()

        df = add_indicators(df)

        if df.empty or len(df) < 25:
            st.error("数据不足，无法计算指标。")
            st.stop()

        yf_titles = get_yfinance_news(ticker)
        ko_titles = get_google_news(f"{ko_name} 주가 뉴스", language="ko")
        en_titles = get_google_news(f"{en_name} stock news", language="en")

        all_auto_news = " ".join(yf_titles + ko_titles + en_titles)
        auto_news_score, auto_good, auto_risk = score_text(all_auto_news)

        manual_news_score, manual_good, manual_risk = score_text(manual_news)

        result = final_prediction(df, auto_news_score, manual_news_score)

        good_sources = result["good_sources"] + auto_good + manual_good
        risk_sources = result["risk_sources"] + auto_risk + manual_risk

        st.subheader(f"{display_name} 综合分析结果")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前价格", f"{result['close']:,} 韩元")
        c2.metric("综合评分", f"{result['final_score']} / 100")
        c3.metric("风险等级", risk_level(result["final_score"]))
        c4.metric("建议仓位", position_suggestion(result["final_score"]))

        st.markdown(f"## {trend_text(result['final_score'])}")

        st.markdown("### 📊 评分拆解")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("技术评分", f"{result['tech_score']} / 100")
        s2.metric("成交量影响", f"{result['volume_score']:+d}")
        s3.metric("自动新闻影响", f"{result['news_score']:+d}")
        s4.metric("手动新闻影响", f"{result['manual_score']:+d}")

        st.markdown("### 📅 当天价格预测")
        t1, t2, t3 = st.columns(3)
        t1.metric("预测中位价", f"{result['today_mid']:,}")
        t2.metric("预测低点", f"{result['today_low']:,}")
        t3.metric("预测高点", f"{result['today_high']:,}")

        st.markdown("### ⏭️ 下一个交易日价格预测")
        n1, n2, n3 = st.columns(3)
        n1.metric("预测中位价", f"{result['next_mid']:,}")
        n2.metric("预测低点", f"{result['next_low']:,}")
        n3.metric("预测高点", f"{result['next_high']:,}")

        st.markdown("### 🧠 文星AI总结")
        st.success(ai_summary(result["final_score"], risk_sources, good_sources))

        st.markdown("### ✅ 最大利好来源 TOP5")
        if good_sources:
            for item in good_sources[:5]:
                st.success(item)
        else:
            st.info("暂无明显利好来源。")

        st.markdown("### 🚨 最大风险来源 TOP5")
        if risk_sources:
            for item in risk_sources[:5]:
                st.warning(item)
        else:
            st.success("暂无明显风险来源。")

        st.markdown("### 📌 技术指标")
        st.write(f"5日均线：{result['ma5']:,}")
        st.write(f"20日均线：{result['ma20']:,}")
        st.write(f"RSI：{result['rsi']}")
        st.write(f"今日成交量 / 20日均量：{result['vol_ratio']}")

        if quantity > 0 and cost_price > 0:
            advice = holding_advice(result["close"], cost_price, quantity, result["final_score"])

            st.markdown("### 💼 我的持仓建议")
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("买入成本", f"{advice['total_cost']:,}")
            h2.metric("当前市值", f"{advice['total_value']:,}")
            h3.metric("当前盈亏", f"{advice['profit']:,}")
            h4.metric("收益率", f"{advice['rate']}%")

            st.markdown(f"## {advice['signal']}")
            st.info(advice["advice"])

            st.write(f"止损参考：{advice['stop_loss']:,} 韩元")
            st.write(f"第一止盈：{advice['take_profit_1']:,} 韩元")
            st.write(f"第二止盈：{advice['take_profit_2']:,} 韩元")

        st.markdown("### 📰 自动新闻标题")
        with st.expander("查看自动抓取新闻"):
            st.write("Yahoo/yfinance 新闻")
            for title in yf_titles[:5]:
                st.write(f"- {title}")

            st.write("Google韩文新闻")
            for title in ko_titles[:5]:
                st.write(f"- {title}")

            st.write("Google英文新闻")
            for title in en_titles[:5]:
                st.write(f"- {title}")

        st.markdown("### 📈 最近60日走势")
        st.line_chart(df["Close"].tail(60))