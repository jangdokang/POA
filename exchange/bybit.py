from exchange.pexchange import ccxt
from model import MarketOrder


class Bybit:
    def __init__(self, key, secret):
        self.future = ccxt.bybit({
            'apiKey': key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        self.spot = ccxt.bybit({
            'apiKey': key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                "defaultType": "spot"
            }
        })
        self.spot.load_markets()
        self.future.load_markets()
        self.order_info: MarketOrder = None

    def parse_quote(self, quote: str):
        if self.order_info.is_futures:
            return quote.replace(".P", "")
        else:
            return quote

    def parse_symbol(self, base: str, quote: str):
        quote = self.parse_quote(quote)
        if self.order_info.is_futures:
            return f"{base}/{quote}:{quote}"
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
        return self.spot.create_order(symbol, type.lower(), side.lower(), amount, price)

    def market_buy(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, buy_percent: float = None):
        # 비용주문
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        return self.market_order(base, quote, type, side, buy_amount, price)

    def market_sell(self, base: str, quote: str, type: str, side: str, amount: float = None, price: float = None, sell_percent: str = None):
        sell_amount = self.get_amount(base, quote, amount, sell_percent)
        return self.market_order(base, quote, type, side, sell_amount)

    def market_entry(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, entry_percent: float = None, leverage: int = None):
        symbol = self.parse_symbol(base, quote)
        side = self.parse_side(side)
        quote = self.parse_quote(quote)
        entry_amount = self.get_amount(base, quote, amount, entry_percent)
        if leverage is not None:
            self.set_leverage(leverage, symbol)
        try:
            return self.future.create_order(symbol, type.lower(), side, abs(entry_amount), params={"position_idx": 0})
        except Exception as e:
            error = str(e)
            if "position idx not match position mode" in error:
                raise Exception("create_order error: 포지션 모드를 원웨이모드로 변경하세요")
            else:
                raise Exception("create_order error")

    def market_close(self, base: str, quote: str, type: str, side: str, amount: float = None, price: float = None, close_percent: str = None):
        symbol = self.parse_symbol(base, quote)
        quote = self.parse_quote(quote)
        side = self.parse_side(side)
        close_amount = self.get_amount(base, quote, amount, close_percent)
        return self.future.create_order(symbol, type.lower(), side, close_amount, params={"reduceOnly": True, "position_idx": 0})

    def get_balance(self, base: str):
        balance = self.future.fetch_free_balance().get(base) if self.order_info.is_crypto and self.order_info.is_futures else self.spot.fetch_free_balance().get(base)
        if balance is None or balance == 0:
            raise Exception("거래할 수량이 없습니다")
        return balance

    def fetch_ticker(self, base: str, quote: str):
        symbol = self.parse_symbol(base, quote)
        if self.order_info.is_futures:
            return self.future.fetch_ticker(symbol)
        else:
            return self.spot.fetch_ticker(symbol)

    def fetch_price(self, base: str, quote: str):
        return self.fetch_ticker(base, quote)["last"]

    def get_futures_position(self, symbol):
        position = self.future.fetch_positions(symbols=[symbol])
        if position:
            balance = position[0].get("contracts")
            if balance is None or balance == 0:
                raise Exception("거래할 수량이 없습니다")
            return balance
        else:
            raise Exception("거래할 수량이 없습니다")

    def set_leverage(self, leverage: float, symbol: str):
        try:
            self.future.set_leverage(leverage, symbol)
        except Exception as e:
            error = str(e)
            if "leverage not modified" in error:
                pass
            else:
                raise Exception(e)
