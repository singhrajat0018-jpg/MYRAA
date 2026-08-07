"""
JSON Portfolio Store
"""

from __future__ import annotations

import json
from pathlib import Path

from ..portfolio.models.holding import Holding
from ..portfolio.models.portfolio import Portfolio
from dataclasses import asdict
from datetime import datetime
from .portfolio_repository import PortfolioRepository


class PortfolioStore(PortfolioRepository):

    def __init__(
        self,
        path: str = "data/portfolio.json",
    ):

        self.path = Path(path)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # --------------------------------------------------

    def load(self) -> Portfolio:

        if not self.path.exists():

            return Portfolio()

        with open(
            self.path,
            "r",
            encoding="utf-8",
        ) as f:

            raw = json.load(f)

        portfolio = Portfolio()

        for item in raw.get("holdings", []):

            if item.get("created_at"):
                item["created_at"] = datetime.fromisoformat(
                    item["created_at"]
                )

            if item.get("last_updated"):
                item["last_updated"] = datetime.fromisoformat(
                    item["last_updated"]
                )

            portfolio.add(
                Holding(**item)
            )

        return portfolio

    # --------------------------------------------------

    def save(

        self,

        portfolio: Portfolio,

    ) -> None:

        holdings = []

        for h in portfolio.holdings:

            data = asdict(h)

            if isinstance(data["created_at"], datetime):
                data["created_at"] = data["created_at"].isoformat()

            if isinstance(data["last_updated"], datetime):
                data["last_updated"] = data["last_updated"].isoformat()

            holdings.append(data)

        with open(

            self.path,

            "w",

            encoding="utf-8",

        ) as f:

            json.dump(

                {

                    "holdings": holdings

                },

                f,

                indent=4,

            )