"""akshare 字段映射 — spec §4.5。

akshare 不同函数返回的中文列名 → 内部英文标准列名。
map_fields(df, indicator) 安全地重命名存在的列, 不抛 KeyError。
"""
from __future__ import annotations

import pandas as pd

FIELD_MAPPINGS: dict[str, dict[str, str]] = {
    "mainflow": {
        "日期": "date",
        "主力净流入-净额": "value",
    },
    "bond_10y": {
        "日期": "date",
        "中国国债收益率10年": "value",
    },
    "shibor_on": {
        "日期": "date",
        "O/N-定价": "value",
    },
    "usd_cny": {
        "日期": "date",
        # BOC 数据: 美元列 = 100 美元兑人民币, 需 ÷100 转真实汇率
        "美元": "raw_value",
    },
    "pmi_mfg": {
        "月份": "date",          # "2026年05月份" 格式
        "制造业-指数": "value",
    },
    "m2": {
        "月份": "date",
        "货币和准货币(M2)-同比增长": "value_yoy",
        "货币(M1)-同比增长": "m1_yoy",
        "流通中的现金(M0)-同比增长": "m0_yoy",
    },
    "cpi": {
        "月份": "date",
        "全国-同比增长": "value_yoy",
        "全国-环比增长": "value_mom",
    },
    "lpr": {
        "TRADE_DATE": "date",
        "LPR1Y": "lpr_1y",
        "LPR5Y": "lpr_5y",
    },
    # ETF 实时行情 (fund_etf_spot_em 33 字段, 用 EM 中文列名映射)
    "etf_realtime": {
        "代码": "code",
        "名称": "name",
        "最新价": "close",
        "IOPV实时估值": "iopv",
        "基金折价率": "discount",
        "昨收": "prev_close",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "涨跌额": "change",
        "涨跌幅": "pct_chg",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "换手率": "turnover",
        "量比": "vol_ratio",
        "外盘": "outer_disk",
        "内盘": "inner_disk",
        "主力净流入-净额": "main_net_inflow",
        "主力净流入-净占比": "main_net_pct",
        "超大单净流入-净额": "super_large_net_inflow",
        "超大单净流入-净占比": "super_large_net_pct",
        "大单净流入-净额": "large_net_inflow",
        "大单净流入-净占比": "large_net_pct",
        "中单净流入-净额": "medium_net_inflow",
        "中单净流入-净占比": "medium_net_pct",
        "小单净流入-净额": "small_net_inflow",
        "小单净流入-净占比": "small_net_pct",
        "最新份额": "shares",
        "流通市值": "float_mkt_cap",
        "总市值": "mkt_cap",
        "更新时间": "update_time",
    },
}


def map_fields(df: pd.DataFrame, indicator: str) -> pd.DataFrame:
    """把 akshare 返回的中文列重命名为内部英文标准列。
    只重命名存在的列, 不抛 KeyError。"""
    if indicator not in FIELD_MAPPINGS:
        return df
    mapping = FIELD_MAPPINGS[indicator]
    rename_cols = {k: v for k, v in mapping.items() if k in df.columns}
    return df.rename(columns=rename_cols)


def parse_month_label(s: str) -> str | None:
    """'2026年05月份' → '2026-05'. 失败返回 None。"""
    if not isinstance(s, str):
        return None
    s = s.replace("月份", "").replace("年", "-").strip()
    # 期望 '2026-05' 格式
    parts = s.split("-")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}-{int(parts[1]):02d}"
    return None