from exchange.pexchange import ccxt, ccxt_async
from exchange.database import db
from exchange.model import MarketOrder
import exchange.error as error


class Upbit:
    def __init__(self, key, secret):
        self.client = ccxt.upbit(
            {
                "apiKey": key,
                "secret": secret,
            }
        )
        self.client.load_markets()
        self.order_info: MarketOrder = None

    def init_info(self, order_info: MarketOrder):
        self.order_info = order_info
        unified_symbol = order_info.unified_symbol
        market = self.client.market(unified_symbol)

        if order_info.amount is not None:
            order_info.amount = float(self.client.amount_to_precision(order_info.unified_symbol, order_info.amount))

        self.client.options["defaultType"] = "spot"

    # async def aclose(self):
    #     await self.spot_async.close()
    def get_ticker(self, symbol: str):
        return self.client.fetch_ticker(symbol)

    def get_price(self, symbol: str):
        return self.get_ticker(symbol)["last"]

    def get_balance(self, base: str) -> float:
        free_balance_by_base = (self.client.fetch_free_balance()).get(base)
        if free_balance_by_base is None or free_balance_by_base == 0:
            raise error.FreeAmountNoneError()
        else:
            return free_balance_by_base

    def get_amount(self, order_info: MarketOrder) -> float:
        if order_info.amount is not None and order_info.percent is not None:
            raise error.AmountPercentBothError()
        elif order_info.amount is not None:
            result = order_info.amount
        elif order_info.percent is not None:
            if self.order_info.side in ("buy"):
                free_quote = self.get_balance(order_info.quote)
                cash = free_quote * order_info.percent / 100
                current_price = self.get_price(order_info.unified_symbol)
                result = cash / current_price
            elif self.order_info.side in ("sell"):
                free_amount = self.get_balance(order_info.base)
                if free_amount is None:
                    raise error.FreeAmountNoneError()
                result = free_amount * order_info.percent / 100
        else:
            raise error.AmountPercentNoneError()
        return result

    def market_order(self, order_info: MarketOrder):
        from exchange.pexchange import retry

        params = {}
        try:
            return retry(
                self.client.create_order,
                order_info.unified_symbol,
                order_info.type.lower(),
                order_info.side,
                order_info.amount,
                order_info.price,
                params,
                order_info=order_info,
                max_attempts=5,
                instance=self,
            )
        except Exception as e:
            raise error.OrderError(e, order_info)

    def market_buy(self, order_info: MarketOrder):
        from exchange.pexchange import retry

        # 비용주문
        buy_amount = self.get_amount(order_info)
        order_info.amount = buy_amount
        order_info.price = self.get_price(order_info.unified_symbol)
        return self.market_order(order_info)

    def market_sell(self, order_info: MarketOrder):
        sell_amount = self.get_amount(order_info)
        order_info.amount = sell_amount
        return self.market_order(order_info)

    def get_order(self, order_id: str):
        return self.client.fetch_order(order_id)

    def get_order_amount(self, order_id: str):
        return self.get_order(order_id)["filled"]
