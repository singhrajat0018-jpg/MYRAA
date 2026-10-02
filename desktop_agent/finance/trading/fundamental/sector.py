"""
MYRAA Trading Intelligence — Sector + Peer Analysis (Part 8)

Compare stock against sector and major peers.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..models import MarketQuote, SectorComparison


class SectorAnalyzer:

    def compare(
        self,
        symbol: str,
        sector: str,
        stock_quote: MarketQuote,
        peer_quotes: Dict[str, MarketQuote],
    ) -> SectorComparison:
        all_changes = [q.day_change_percent for q in peer_quotes.values()]
        if symbol.upper() in {s.upper() for s in peer_quotes}:
            peer_changes = [q.day_change_percent for s, q in peer_quotes.items() if s.upper() != symbol.upper()]
        else:
            peer_changes = all_changes

        sector_avg = sum(peer_changes) / len(peer_changes) if peer_changes else 0.0
        stock_change = stock_quote.day_change_percent
        relative = stock_change - sector_avg

        sorted_peers = sorted(peer_quotes.items(), key=lambda x: x[1].day_change_percent, reverse=True)
        rank = 1
        for i, (s, q) in enumerate(sorted_peers, 1):
            if q.day_change_percent <= stock_change:
                rank = i
                break
        else:
            rank = len(sorted_peers) + 1

        total = len(peer_quotes) + 1
        if relative > 2:
            classification = "OUTPERFORMER"
        elif relative < -2:
            classification = "UNDERPERFORMER"
        elif abs(relative) < 0.5:
            classification = "SECTOR_DRIVEN"
        else:
            classification = "STOCK_SPECIFIC"

        return SectorComparison(
            sector=sector,
            symbol=symbol,
            sector_avg_change=sector_avg,
            stock_change=stock_change,
            relative_strength=relative,
            sector_rank=rank,
            total_in_sector=total,
            classification=classification,
        )
