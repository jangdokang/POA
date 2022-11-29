from .pexchange import ccxt, ccxt_async, httpx
from model import MarketOrder


class Binance:
    def __init__(self, key, secret):
        self.future = ccxt.binance({
            'apiKey': key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        self.future_async = ccxt_async.binance({
            'apiKey': key,
            'secret': secret,
            'options': {
                'defaultType': 'future'
            }
        })
        self.spot = ccxt.binance({
            'apiKey': key,
            'secret': secret,
        })
        self.spot_async = ccxt_async.binance({
            'apiKey': key,
            'secret': secret,
        })
        self.spot.load_markets()
        self.future.load_markets()
        self.order_info: MarketOrder = None

    def parse_quote(self, quote: str):
        if self.order_info.is_futures:
            return quote.replace("PERP", "")
        else:
            return quote

    def parse_symbol(self, base: str, quote: str):
        quote = self.parse_quote(quote)
        if self.order_info.is_futures:
            return f"{base}/{quote}"
        else:
            return f"{base}/{quote}"

    def parse_side(self, side: str):
        if side.startswith("entry/") or side.startswith("close/"):
            return side.split("/")[-1]
        else:
            return side

    def get_amount(self, base, quote, amount, percent) -> float:
        if amount is not None and percent is not None:
            raise Exception("amount와 percent는 동시에 사용할 수 없습니다")
        elif amount is not None:
            result = amount
        elif percent is not None:
            if self.order_info.side in ("buy", "entry/buy", "entry/sell"):
                cash = self.get_balance(quote) * percent/100
                current_price = self.fetch_price(base, quote)
                result = cash / current_price
            elif self.order_info.side in ("sell", "close/buy", "close/sell"):
                symbol = self.parse_symbol(base, quote)
                free_amount = self.get_futures_position(symbol) if self.order_info.is_crypto and self.order_info.is_futures else self.get_balance(base)
                result = free_amount * float(percent)/100
        else:
            raise Exception("amount와 percent 중 하나는 입력해야 합니다")
        return result

    def market_order(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        return self.spot.create_order(symbol, type.lower(), side.lower(), amount)

    async def market_order_async(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        return await self.spot_async.create_order(symbol, type.lower(), side.lower(), amount)

    def market_buy(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, buy_percent: float = None):
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        return self.market_order(base, quote, type, side, buy_amount)

    async def market_buy_async(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, buy_percent: float = None):
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        return await self.market_order_async(base, quote, type, side, buy_amount)

    def market_sell(self, base: str, quote: str, type: str, side: str, amount: float, price: str = None, sell_percent: float = None):
        sell_amount = self.get_amount(base, quote, amount, sell_percent)
        return self.market_order(base, quote, type, side, sell_amount)

    async def market_sell_async(self, base: str, quote: str, type: str, side: str, amount: float, price: str = None, sell_percent: float = None):
        sell_amount = self.get_amount(base, quote, amount, sell_percent)
        return await self.market_order_async(base, quote, type, side, sell_amount)

    def market_entry(self, base: str, quote: str, type: str, side: str, amount: float, price: str = None, entry_percent: float = None, leverage: int = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        quote = self.parse_quote(quote)
        entry_amount = self.get_amount(base, quote, amount, entry_percent)
        if leverage is not None:
            self.set_leverage(leverage, symbol)
        return self.future.create_order(symbol, type.lower(), side, abs(entry_amount))

    # def market_stop_order(self, base: str, quote: str, type: str, side: str, amount: float, price: float, stop_price: float):
    #     symbol = f"{base}/{quote}"
    #     return self.future.create_stop_market_order(symbol, type.lower(), side.lower(), amount, price, {"stopPrice": stop_price})

    def market_sltp_order(self, base: str, quote: str, type: str, side: str, amount: float, stop_price: float, profit_price: float):
        symbol = self.parse_symbol(base, quote)
        inverted_side = 'sell' if side.lower() == 'buy' else 'buy'  # buy면 sell, sell이면 buy * 진입 포지션과 반대로 주문 넣어줘 야함
        self.future.create_order(symbol, "STOP_MARKET", inverted_side, amount, None, {"stopPrice": stop_price, "newClientOrderId": "STOP_MARKET"})                   # STOP LOSS 오더
        self.future.create_order(symbol, "TAKE_PROFIT_MARKET", inverted_side, amount, None, {"stopPrice": profit_price, "newClientOrderId": "TAKE_PROFIT_MARKET"})   # TAKE profit 오더

        # response = self.future.private_post_order_oco({
        #     'symbol': self.future.market(symbol)['id'],
        #     'side': 'BUY',  # SELL, BUY
        #     'quantity': self.future.amount_to_precision(symbol, amount),
        #     'price': self.future.price_to_precision(symbol, profit_price),
        #     'stopPrice': self.future.price_to_precision(symbol, stop_price),
        #     # 'stopLimitPrice': self.future.price_to_precision(symbol, stop_limit_price),  # If provided, stopLimitTimeInForce is required
        #     # 'stopLimitTimeInForce': 'GTC',  # GTC, FOK, IOC
        #     # 'listClientOrderId': exchange.uuid(),  # A unique Id for the entire orderList
        #     # 'limitClientOrderId': exchange.uuid(),  # A unique Id for the limit order
        #     # 'limitIcebergQty': exchangea.amount_to_precision(symbol, limit_iceberg_quantity),
        #     # 'stopClientOrderId': exchange.uuid()  # A unique Id for the stop loss/stop loss limit leg
        #     # 'stopIcebergQty': exchange.amount_to_precision(symbol, stop_iceberg_quantity),
        #     # 'newOrderRespType': 'ACK',  # ACK, RESULT, FULL
        # })

    async def market_entry_async(self, base: str, quote: str, type: str, side: str, amount: float, price: str = None, entry_percent: float = None, leverage: int = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        quote = self.parse_quote(quote)
        entry_amount = self.get_amount(base, quote, amount, entry_percent)
        if leverage is not None:
            self.set_leverage(leverage, symbol)
        return await self.future_async.create_order(symbol, type.lower(), side, abs(entry_amount))

    def market_close(self, base: str, quote: str, type: str, side: str, amount: float = None, price: str = None, close_percent: str = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        quote = self.parse_quote(quote)
        close_amount = self.get_amount(base, quote, amount, close_percent)
        return self.future.create_order(symbol, type.lower(), side, close_amount, params={"reduceOnly": True})

    async def market_close_async(self, base: str, quote: str, type: str, side: str, amount: float = None, price: str = None, close_percent: str = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        quote = self.parse_quote(quote)
        close_amount = self.get_amount(base, quote, amount, close_percent)
        return await self.future_async.create_order(symbol, type.lower(), side, close_amount, params={"reduceOnly": True})

    def set_leverage(self, leverage, symbol):
        self.future.set_leverage(leverage, symbol)

    def fetch_ticker(self, base: str, quote: str):
        symbol = self.parse_symbol(base, quote)
        if self.order_info.is_futures:
            return self.future.fetch_ticker(symbol)
        else:
            return self.spot.fetch_ticker(symbol)

    def fetch_price(self, base: str, quote: str):
        return self.fetch_ticker(base, quote)["last"]

    def get_balance(self, base: str):
        balance = self.future.fetch_free_balance().get(base) if self.order_info.is_crypto and self.order_info.is_futures else self.spot.fetch_free_balance().get(base)
        if balance is None or balance == 0:
            raise Exception("거래할 수량이 없습니다")
        return balance

    def get_futures_position(self, symbol):
        position = self.future.fetch_positions_risk(symbols=[symbol])
        if position:
            balance = position[0].get("contracts")
            if balance is None or balance == 0:
                raise Exception("거래할 수량이 없습니다")
            return balance
        else:
            raise Exception("거래할 수량이 없습니다")

    def get_listen_key(self):
        url = 'https://fapi.binance.com/fapi/v1/listenKey'

        listenkey = httpx.post(url, headers={'X-MBX-APIKEY': self.future.apiKey}).json()["listenKey"]
        return listenkey
