from exchange.pexchange import ccxt, ccxt_async
from exchange.database import db
from model import MarketOrder


class Upbit():
    def __init__(self, key, secret):
        self.spot = ccxt.upbit({
            'apiKey': key,
            'secret': secret,

        })
        self.spot.load_markets()
        self.spot_async = ccxt_async.upbit({
            'apiKey': key,
            'secret': secret,
        })
        self.order_info: MarketOrder = None

    async def aclose(self):
        await self.spot_async.close()

    def market_buy(self, base, quote, type, side, amount, price=None, buy_percent: float = None):
        # 비용주문
        symbol = f"{base}/{quote}"
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        return self.spot.create_order(symbol, type.lower(), side.lower(), buy_amount, price)

    async def market_buy_async(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, buy_percent: float = None):
        symbol = f"{base}/{quote}"
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        try:
            result = await self.spot_async.create_order(symbol, type.lower(), side.lower(), buy_amount, price)
        except:
            raise Exception()
        finally:
            await self.aclose()
        return result

    def market_sell(self, base, quote, type, side, amount: float, price: float = None, sell_percent: str = None):
        symbol = f"{base}/{quote}"
        result = None
        sell_amount = self.get_amount(base, quote, amount, sell_percent)
        result = self.spot.create_order(symbol, type.lower(), side.lower(), sell_amount)
        return result

    async def market_sell_async(self, base, quote, type, side, amount: float, price: float = None, sell_percent: str = None):
        symbol = f"{base}/{quote}"
        result = None
        sell_amount = self.get_amount(base, quote, amount, sell_percent)
        try:
            result = await self.spot_async.create_order(symbol, type.lower(), side.lower(), sell_amount)
        except:
            raise Exception()
        finally:
            await self.aclose()

        return result

    def get_amount(self, base, quote, amount, percent) -> float:
        if amount is not None and percent is not None:
            raise Exception("amount와 percent는 동시에 사용할 수 없습니다")
        elif amount is not None:
            result = amount
        elif percent is not None:
            if self.order_info.side in ("buy"):
                cash = self.get_balance(quote) * percent/100
                current_price = self.fetch_price(base, quote)
                result = cash / current_price
            elif self.order_info.side in ("sell"):
                free_amount = self.get_balance(base)
                result = free_amount * float(percent)/100
        else:
            raise Exception("amount와 percent 중 하나는 입력해야 합니다!")
        return result

    def get_balance(self, base) -> float:
        return (self.spot.fetch_free_balance()).get(base)

    def fetch_ticker(self, base: str, quote: str):
        symbol = f"{base}/{quote}"
        return self.spot.fetch_ticker(symbol)

    def fetch_price(self, base: str, quote: str):
        return self.fetch_ticker(base, quote)["last"]
