import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import feedparser
import requests

from urllib.parse import quote
from datetime import datetime

st.set_page_config(
    page_title="文星AI交易系统 Pro",
    page_icon="📈",
    layout="wide"
)

# ===== 专业界面 =====

st.markdown("""
<style>

.main {
    background-color: #0E1117;
}

div[data-testid="stMetric"]{
    background:#1E222D;
    border-radius:15px;
    padding:15px;
    border:1px solid #333;
}

.stAlert{
    border-radius:12px;
}

</style>
""", unsafe_allow_html=True)

# ===== 股票数据库 =====

COMMON_STOCKS = {

    "SK海力士":{
        "ticker":"000660.KS",
        "ko":"SK하이닉스",
        "en":"SK hynix"
    },

    "三星电子":{
        "ticker":"005930.KS",
        "ko":"삼성전자",
        "en":"Samsung Electronics"
    },

    "三星电机":{
        "ticker":"009150.KS",
        "ko":"삼성전기",
        "en":"Samsung Electro-Mechanics"
    },

    "现代汽车":{
        "ticker":"005380.KS",
        "ko":"현대차",
        "en":"Hyundai Motor"
    },

    "斗山能源":{
        "ticker":"034020.KS",
        "ko":"두산에너빌리티",
        "en":"Doosan Enerbility"
    },

    "LS ELECTRIC":{
        "ticker":"010120.KS",
        "ko":"LS ELECTRIC",
        "en":"LS Electric"
    },

    "대한전선":{
        "ticker":"001440.KS",
        "ko":"대한전선",
        "en":"Taihan Cable"
    }

}

# ===== 顶部 =====

st.title("📈 文星AI交易系统 Pro")

st.caption(
    "V3.0 Professional ｜ AI预测 ｜ 新闻分析 ｜ 风险雷达 ｜ 仓位管理"
)

st.warning(
    "本系统仅供参考，不构成投资建议。股市有风险，投资需谨慎。"
)# ===== 工具函数 =====

def safe_float(value):
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

    return df.dropna()


def add_indicators(df):

    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).