import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="韩股AI预测助手",
    page_icon="📈",
    layout="centered"
)

STOCKS = {
    "SK海力士": "000660.KS",
    "三星电子": "005930.KS",
    "三星电机": "009150.KS",
}

st.title("📈 韩股AI预测助手")
st.caption("手机版 V1.1｜适合海力士、三星电子、三星电机短线参考")
st.warning("结果仅供参考，不构成投资建议。股市有风险，操作需谨慎。")


def safe_float(value):
    """把 yfinance 返回的各种格式安全转成普通数字"""
    if isinstance(value, pd.Series):
        return float(value.iloc[0])
    if isinstance(value, np.ndarray):
        return float(value.flatten()[0])
    return float(value)


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

    df = df.dropna()
    return df


def make_prediction(df):
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

    expected_change = (score - 50) / 1000
    predicted_price = close * (1 + expected_change)

    daily_range = max(volatility * 2, 0.025)
    predicted_low = predicted_price * (1 - daily_range)
    predicted_high = predicted_price * (1 + daily_range)

    if score >= 75:
        trend = "强势偏多"
    elif score >= 60:
        trend = "偏多"
    elif score >= 45:
        trend = "震荡"
    elif score >= 35:
        trend = "偏弱"
    else:
        trend = "弱势"

    return {
        "close": round(close),
        "ma5": round(ma5),
        "ma20": round(ma20),
        "rsi": round(rsi, 2),
        "score": round(score),
        "trend": trend,
        "predicted_price": round(predicted_price),
        "predicted_low": round(predicted_low),
        "predicted_high": round(predicted_high),
    }


def get_advice(current_price, cost_price, quantity, score):
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

    if profit_rate >= 20 and score < 60:
        advice = "盈利较大，趋势转弱，建议分批止盈。"
        signal = "🔴 减仓 / 止盈"
    elif profit_rate >= 12 and score >= 60:
        advice = "盈利不错，趋势仍强，可以继续持有，但要设置移动止盈。"
        signal = "🟡 持有"
    elif profit_rate >= 5 and score >= 55:
        advice = "小幅盈利，趋势还可以，继续观察。"
        signal = "🟡 持有"
    elif profit_rate < -5 and score < 45:
        advice = "已经亏损且趋势偏弱，建议控制风险，跌破止损位考虑减仓。"
        signal = "🔴 风险控制"
    elif score >= 70:
        advice = "趋势较强，可以持有，不建议盲目追高。"
        signal = "🟢 偏强"
    elif score >= 55:
        advice = "趋势中性偏多，适合持有观察。"
        signal = "🟡 观察"
    else:
        advice = "趋势不强，先观望，不建议重仓加仓。"
        signal = "⚪ 观望"

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


stock_name = st.selectbox("选择股票", list(STOCKS.keys()))
ticker = STOCKS[stock_name]

quantity = st.number_input("持仓数量", min_value=0, value=1, step=1)
cost_price = st.number_input("你的成本价（韩元）", min_value=0, value=0, step=1000)

if st.button("开始分析"):
    with st.spinner("正在获取行情并分析..."):
        df = get_stock_data(ticker)

        if df is None or df.empty:
            st.error("行情数据获取失败，请稍后再试。")
        else:
            df = add_indicators(df)

            if df.empty:
                st.error("数据不足，无法计算指标。")
            else:
                result = make_prediction(df)

                st.subheader(f"{stock_name} 分析结果")

                st.metric("当前价格", f"{result['close']:,} 韩元")
                st.metric("趋势评分", f"{result['score']} / 100")
                st.metric("趋势判断", result["trend"])

                st.markdown("### 明日价格预测")
                col1, col2, col3 = st.columns(3)
                col1.metric("预测中位价", f"{result['predicted_price']:,}")
                col2.metric("预测低点", f"{result['predicted_low']:,}")
                col3.metric("预测高点", f"{result['predicted_high']:,}")

                st.markdown("### 技术指标")
                st.write(f"5日均线：{result['ma5']:,}")
                st.write(f"20日均线：{result['ma20']:,}")
                st.write(f"RSI：{result['rsi']}")

                if quantity > 0 and cost_price > 0:
                    advice = get_advice(
                        result["close"],
                        cost_price,
                        quantity,
                        result["score"]
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