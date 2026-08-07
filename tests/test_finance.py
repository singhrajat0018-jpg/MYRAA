"""
Finance Integration Test

Run:

    python -m tests.test_finance
"""

from desktop_agent.finance.portfolio.portfolio_manager import PortfolioManager
from desktop_agent.finance.market.provider_manager import ProviderManager
from desktop_agent.finance.market.providers.yahoo_provider import YahooProvider
from desktop_agent.finance.finance_service import FinanceService


def line():
    print("=" * 70)


def main():

    line()
    print("MYRAA FINANCE INTEGRATION TEST")
    line()

    # -----------------------------------------------------
    # Portfolio
    # -----------------------------------------------------

    portfolio = PortfolioManager()

    portfolio.buy(
        symbol="WOCKPHARMA",
        company_name="Wockhardt",
        quantity=10,
        average_price=1771,
    )

    portfolio.buy(
        symbol="TCS",
        company_name="Tata Consultancy Services",
        quantity=5,
        average_price=3500,
    )

    print("\n[PASS] PortfolioManager")

    # -----------------------------------------------------
    # Provider
    # -----------------------------------------------------

    provider = ProviderManager()

    provider.register(
        "yahoo",
        YahooProvider(),
    )

    provider.use("yahoo")

    print("[PASS] ProviderManager")

    # -----------------------------------------------------
    # Yahoo Quotes
    # -----------------------------------------------------

    quotes = provider.get_quotes(
        ["WOCKPHARMA", "TCS"]
    )

    print("[PASS] YahooProvider")

    print("\nDownloaded Quotes")

    for symbol, quote in quotes.items():

        print("--------------------------------")

        print("Symbol :", symbol)

        print("Price  :", quote.current_price)

        print("Prev   :", quote.previous_close)

        print("Change :", quote.day_change_percent)

    # -----------------------------------------------------
    # Finance Service
    # -----------------------------------------------------

    finance = FinanceService(
        portfolio=portfolio,
        provider=provider,
    )

    print("\n[PASS] FinanceService Created")

    # -----------------------------------------------------
    # Events
    # -----------------------------------------------------

    events = finance.process()

    print("\nFinance Events")

    if not events:

        print("No alerts generated.")

    else:

        for i, event in enumerate(events, start=1):

            print("--------------------------------")

            print(f"Event #{i}")

            print("Title      :", event.title)

            print("Message    :", event.message)

            print("Severity   :", event.severity)

            print("Data")

            for key, value in event.data.items():

                print(f"   {key:<18}: {value}")

    line()

    print("Finance Integration Test Completed")

    line()


if __name__ == "__main__":
    main()