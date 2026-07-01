"""SectorProvider — 板块/概念 (行业 + 概念) 数据源.

支持的 indicator:
  - sector_snapshot (ak.stock_board_industry_spot_em + stock_board_concept_spot_em)
  - sector_history  (ak.stock_board_industry_hist_em + stock_board_concept_hist_em)

akshare 字段都是中文, 这里做映射到英文 (跟 cache / API 一致).
"""
from backend.providers.sector.provider import SectorProvider
from backend.providers.sector.backup import SectorBackupProvider

__all__ = ["SectorProvider", "SectorBackupProvider"]