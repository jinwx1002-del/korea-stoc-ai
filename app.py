import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="韩股AI预测助手",
    page_icon="📈",
    layout="centered"
)

COMMON_STOCKS = {
    "SK海力士": {
        "ticker": "000660.KS",
        "keywords": ["SK hynix", "Hynix", "HBM", "DRAM", "memory chip", "AI memory"]
    },
    "三星电子": {
        "ticker": "005930.KS",
        "keywords": ["Samsung Electronics", "Samsung", "HBM", "DRAM", "semiconductor", "AI chip"]
    },
    "三星电机": {
        "ticker": "009150.KS",
        "keywords": ["Samsung Electro-Mechanics", "Samsung Electro", "MLCC", "FCBGA", "silicon capacitor", "AI server"]
    },
    "现代汽车": {
        "ticker": "005380.KS",
        "keywords": ["Hyundai Motor", "Hyundai", "EV", "automobile", "car"]
    },
    "斗山能源": {
        "ticker": "034020.KS",
        "keywords": ["Doosan Enerbility", "Doosan", "nuclear", "SMR", "energy"]
    },
    "LS ELECTRIC": {
        "ticker": "010120.KS",
        "keywords": ["LS Electric", "LS ELECTRIC", "power equipment", "electric grid", "transformer"]
    },
    "대한전선": {
        "ticker": "001440.KS",
        "keywords": ["Taihan Cable", "대한전선", "cable", "power cable"]
    },
}

POSITIVE_WORDS = [
    "rise", "rises", "rally", "surge", "surges", "jump", "jumps", "gain", "gains",
    "beat", "beats", "strong", "growth", "record", "upgrade", "upgraded",
    "target raised", "raises target", "buy rating", "outperform",
    "order", "contract", "supply", "demand", "AI", "HBM", "DRAM", "Nvidia",
    "Micron", "server", "accelerator", "profit", "revenue", "shipments",
    "price increase", "memory prices", "boom"
]

NEGATIVE_WORDS = [
    "fall", "falls", "drop", "drops", "decline", "declines", "slump", "selloff",
    "weak", "loss", "miss", "cut", "downgrade", "downgraded",
    "strike", "lawsuit", "delay", "delayed", "risk", "concern", "concerns",
    "tariff", "export restriction", "ban", "investigation", "shortage",
    "slowdown", "pressure", "volatile", "warning"
]

st.title("📈 韩股AI预测助手")
st.caption("手机版 V2.2｜任意韩股代码 + 技术指标 + 新闻情绪 + 成交量")
st.warning("结果仅供参考，不构成投资建议。股市有风险，操作需谨慎。")


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

    df = df.dropna()
    return df


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
    df["PRICE_CHANGE"] = df["Close"].pct_change()

    df = df.dropna()
    return df


def get_news_score(ticker):
    positive_hits = []
    negative_hits = []
    news_titles = []

    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        if not news:
            return {
                "news_score": 0,
                "news_count": 0,
                "positive_hits": [],
                "negative_hits": [],
                "news_titles": [],
                "news_comment": "暂时没有抓取到相关新闻，新闻评分按中性处理。"
            }

        for item in news[:10]:
            title = item.get("title", "")
            if not title:
                continue

            news_titles.append(title)
            title_lower = title.lower()

            for word in POSITIVE_WORDS:
                if word.lower() in title_lower:
                    positive_hits.append(word)

            for word in NEGATIVE_WORDS:
                if word.lower() in title_lower:
                    negative_hits.append(word)

        score = len(positive_hits) * 3 - len(negative_hits) * 4
        score = max(-20, min(20, score))

        if score > 8:
            comment = "新闻情绪偏利好。"
        elif score > 0:
            comment = "新闻情绪小幅偏多。"
        elif score < -8:
            comment = "新闻情绪偏利空。"
        elif score < 0:
            comment = "新闻情绪小幅偏空。"
        else:
            comment = "新闻情绪中性。"

        return {
            "news_score": score,
            "news_count": len(news_titles),
            "positive_hits": list(set(positive_hits))[:10],
            "negative_hits": list(set(negative_hits))[:10],
            "news_titles": news_titles[:5],
            "news_comment": comment
        }

    except Exception:
        return {
            "news_score": 0,
            "news_count": 0,
            "positive_hits": [],
            "negative_hits": [],
            "news_titles": [],
            "news_comment": "新闻数据读取失败，新闻评分按中性处理。"
        }


def get_volume_score(df):
    latest = df.iloc[-1]

    close = safe_float(latest["Close"])
    previous_close = safe_float(df.iloc[-2]["Close"])
    volume = safe_float(latest["Volume"])
    volume_ma20 = safe_float(latest["VOLUME_MA20"])

    price_change = (close - previous_close) / previous_close * 100

    if volume_ma20 <= 0:
        return {
            "volume_score": 0,
            "volume_ratio": 0,
            "volume_comment": "成交量数据不足，成交量评分按中性处理。"
        }

    volume_ratio = volume / volume_ma20
    score = 0

    if price_change > 1 and volume_ratio >= 1.5:
        score = 12
        comment = "放量上涨，说明资金参与度较高，短线偏利好。"
    elif price_change > 0 and volume_ratio >= 1.2:
        score = 8
        comment = "温和放量上涨，趋势可信度提高。"
    elif price_change > 0 and volume_ratio < 0.8:
        score = -5
        comment = "上涨但缩量，追高要谨慎，可能有冲高回落风险。"
    elif price_change < -1 and volume_ratio >= 1.5:
        score = -12
        comment = "放量下跌，说明抛压较大，短线风险提高。"
    elif price_change < 0 and volume_ratio >= 1.2:
        score = -8
        comment = "下跌伴随放量，资金面偏弱。"
    elif price_change < 0 and volume_ratio < 0.8:
        score = 3
        comment = "缩量下跌，可能只是正常回调，风险相对可控。"
    elif volume_ratio >= 2:
        score = 5
        comment = "成交量明显放大，但方向不强，需要结合价格突破判断。"
    else:
        score = 0
        comment = "成交量正常，资金面没有明显异常。"

    return {
        "volume_score": score,
        "volume_ratio": round(volume_ratio, 2),
        "volume_comment": comment
    }


def make_technical_prediction(df):
    latest = df.iloc[-1]

    close = safe_float(latest["Close"])
    ma5 = safe_float(latest["MA5"])
    ma20 = safe_float(latest["MA20"])
    rsi = safe_float(latest["RSI"])
    macd = safe_float(latest["MACD"])
    macd_signal = safe_float(latest["MACD_SIGNAL"])
    volatility = safe_float(latest["VOLATILITY"])

    score = 50

    if close > ma5:
        score += 10
    else:
        score -= 10

    if close > ma20:
        score += 15
    else:
        score -= 15

    if ma5 > ma20:
        score += 10
    else:
        score -= 10

    if macd > macd_signal:
        score += 10
    else:
        score -= 10

    if rsi >= 75:
        score -= 15
    elif rsi >= 65:
        score -= 5
    elif rsi <= 30:
        score += 10

    score = max(0, min(100, score))

    return {
        "close": close,
        "ma5": ma5,
        "ma20": ma20,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "volatility": volatility,
        "technical_score": round(score)
    }


def make_final_prediction(technical, news_result, volume_result):
    close = technical["close"]
    volatility = technical["volatility"]

    technical_score = technical["technical_score"]
    news_score = news_result["news_score"]
    volume_score = volume_result["volume_score"]

    final_score = technical_score + news_score + volume_score
    final_score = max(0, min(100, final_score))

    expected_change = (final_score - 50) / 1000
    predicted_price = close * (1 + expected_change)

    daily_range = max(volatility * 2, 0.025)
    predicted_low = predicted_price * (1 - daily_range)
    predicted_high = predicted_price * (1 + daily_range)

    if final_score >= 75:
        trend = "强势偏多"
    elif final_score >= 60:
        trend = "偏多"
    elif final_score >= 45:
        trend = "震荡"
    elif final_score >= 35:
        trend = "偏弱"
    else:
        trend = "弱势"

    return {
        "close": round(close),
        "technical_score": round(technical_score),
        "news_score": round(news_score),
        "volume_score": round(volume_score),
        "final_score": round(final_score),
        "trend": trend,
        "predicted_price": round(predicted_price),
        "predicted_low": round(predicted_low),
        "predicted_high": round(predicted_high),
        "ma5": round(technical["ma5"]),
        "ma20": round(technical["ma20"]),
        "rsi": round(technical["rsi"], 2),
    }


def get_advice(current_price, cost_price, quantity, final_score, news_score, volume_score):
    total_cost = cost_price * quantity
    total_value = current_price * quantity
    profit = total_value - total_cost

    if cost_price > 0:
        profit_rate = (current_price - cost_price) / cost_price * 100
    else:
        profit_rate = 0

    stop_loss = current_price * 0.94
    take_profit_1 = current_price * 1.05
    take_profit_2 = current_price * 1.10

    if profit_rate >= 20 and final_score < 60:
        advice = "盈利较大，但综合评分转弱，建议分批止盈。"
        signal = "🔴 减仓 / 止盈"
    elif profit_rate >= 12 and final_score >= 60:
        advice = "盈利不错，综合趋势仍偏强，可以继续持有，但要设置移动止盈。"
        signal = "🟡 持有"
    elif profit_rate >= 5 and final_score >= 55:
        advice = "小幅盈利，趋势还可以，继续观察。"
        signal = "🟡 持有"
    elif profit_rate < -5 and final_score < 45:
        advice = "已经亏损且综合趋势偏弱，建议控制风险，跌破止损位考虑减仓。"
        signal = "🔴 风险控制"
    elif final_score >= 75:
        advice = "技术面、消息面和成交量综合偏强，可以持有，但不建议盲目追高。"
        signal = "🟢 偏强"
    elif final_score >= 60:
        advice = "综合趋势偏多，适合持有观察。"
        signal = "🟡 持有观察"
    elif final_score >= 45:
        advice = "综合趋势震荡，适合少操作，等待方向明确。"
        signal = "⚪ 震荡观望"
    else:
        advice = "综合趋势偏弱，建议谨慎，不建议加仓。"
        signal = "🔴 谨慎"

    if news_score <= -10:
        advice += " 新闻情绪偏空，开盘后要特别注意快速回落。"
    elif news_score >= 10:
        advice += " 新闻情绪偏利好，短线资金关注度可能较高。"

    if volume_score <= -8:
        advice += " 成交量显示抛压偏大，注意不要硬扛。"
    elif volume_score >= 8:
        advice += " 成交量配合较好，说明资金参与度较高。"

    return {
        "total_cost": round(total_cost),
        "total_value": round(total_value),
        "profit": round(profit),
        "profit_rate": round(profit_rate, 2),
        "stop_loss": round(stop_loss),
        "take_profit_1": round(take_profit_1),
        "take_profit_2": round(take_profit_2),
        "advice": advice,
        "signal": signal,
    }


mode = st.radio(
    "选择股票方式",
    ["常用股票", "输入韩股代码"],
    horizontal=True
)

if mode == "常用股票":
    stock_name = st.selectbox("选择股票", list(COMMON_STOCKS.keys()))
    ticker = COMMON_STOCKS[stock_name]["ticker"]
    display_name = stock_name
else:
    stock_code = st.text_input("输入6位韩股代码，例如 000660、005930、009150", value="000660")
    ticker = normalize_korean_ticker(stock_code)

    if ticker is None:
        st.error("请输入正确的6位韩股代码，例如 000660。")
        st.stop()

    display_name = f"自定义股票 {ticker}"

quantity = st.number_input("持仓数量", min_value=0, value=1, step=1)
cost_price = st.number_input("你的成本价（韩元）", min_value=0, value=0, step=1000)

if st.button("开始分析"):
    with st.spinner("正在获取行情、计算技术指标、分析新闻情绪和成交量..."):
        df = get_stock_data(ticker)

        if df is None or df.empty:
            st.error("行情数据获取失败。可能原因：代码错误、该股票不是KOSPI代码，或yfinance暂时无数据。")
        else:
            df = add_indicators(df)

            if df.empty or len(df) < 25:
                st.error("数据不足，无法计算指标。")
            else:
                technical = make_technical_prediction(df)
                news_result = get_news_score(ticker)
                volume_result = get_volume_score(df)
                result = make_final_prediction(technical, news_result, volume_result)

                st.subheader(f"{display_name} 综合分析结果")

                st.metric("当前价格", f"{result['close']:,} 韩元")
                st.metric("最终综合评分", f"{result['final_score']} / 100")
                st.metric("趋势判断", result["trend"])

                st.markdown("### 评分拆解")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("技术评分", f"{result['technical_score']} / 100")
                col_b.metric("新闻影响", f"{result['news_score']:+d}")
                col_c.metric("成交量影响", f"{result['volume_score']:+d}")

                st.markdown("### 明日价格预测")
                col1, col2, col3 = st.columns(3)
                col1.metric("预测中位价", f"{result['predicted_price']:,}")
                col2.metric("预测低点", f"{result['predicted_low']:,}")
                col3.metric("预测高点", f"{result['predicted_high']:,}")

                st.markdown("### 技术指标")
                st.write(f"5日均线：{result['ma5']:,}")
                st.write(f"20日均线：{result['ma20']:,}")
                st.write(f"RSI：{result['rsi']}")

                st.markdown("### 成交量分析")
                st.write(f"今日成交量 / 20日均量：{volume_result['volume_ratio']} 倍")
                st.info(volume_result["volume_comment"])

                st.markdown("### 新闻情绪")
                st.write(f"相关新闻数量：{news_result['news_count']}")
                st.info(news_result["news_comment"])

                if news_result["positive_hits"]:
                    st.write("利好关键词：")
                    st.write("、".join(news_result["positive_hits"]))

                if news_result["negative_hits"]:
                    st.write("利空关键词：")
                    st.write("、".join(news_result["negative_hits"]))

                if news_result["news_titles"]:
                    st.write("抓取到的新闻标题：")
                    for title in news_result["news_titles"]:
                        st.write(f"- {title}")

                if quantity > 0 and cost_price > 0:
                    advice = get_advice(
                        result["close"],
                        cost_price,
                        quantity,
                        result["final_score"],
                        result["news_score"],
                        result["volume_score"]
                    )

                    st.markdown("### 我的持仓建议")
                    st.metric("买入成本", f"{advice['total_cost']:,} 韩元")
                    st.metric("当前市值", f"{advice['total_value']:,} 韩元")
                    st.metric("当前盈亏", f"{advice['profit']:,} 韩元")
                    st.metric("收益率", f"{advice['profit_rate']}%")

                    st.markdown(f"## {advice['signal']}")
                    st.info(advice["advice"])

                    st.markdown("### 参考价位")
                    st.write(f"止损参考：{advice['stop_loss']:,} 韩元")
                    st.write(f"第一止盈：{advice['take_profit_1']:,} 韩元")
                    st.write(f"第二止盈：{advice['take_profit_2']:,} 韩元")

                st.markdown("### 最近60日走势")
                st.line_chart(df["Close"].tail(60))