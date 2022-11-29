from exchange.pexchange import ccxt
from exchange.database import db
from model import MarketOrder


class Bitget:
    def __init__(self, key, secret, passphrase=None):
        self.spot = ccxt.bitget({
            'apiKey': key,
            'secret': secret,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        self.future = ccxt.bitget({
            'apiKey': key,
            'secret': secret,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
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

    def market_order(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None):
        symbol = self.parse_symbol(base, quote)
        return self.spot.create_order(symbol, type.lower(), side.lower(), amount, price)

    def market_buy(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, buy_percent: float = None):
        # 비용주문
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        return self.market_order(base, quote, type, side, buy_amount, price)

    def market_sell(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, sell_percent: str = None):
        result = None
        sell_amount = self.get_amount(base, quote, amount, sell_percent)
        result = self.market_order(base, quote, type, side, sell_amount)
        return result

    def market_entry(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None,  entry_percent: float = None, leverage=None):
        symbol = self.parse_symbol(base, quote)
        quote = self.parse_quote(quote)
        side = self.parse_side(side)
        entry_amount = self.get_amount(base, quote, amount, entry_percent)
        if leverage is not None:
            self.set_leverage(leverage, symbol, side)
        return self.future.create_order(symbol, type.lower(), side, abs(entry_amount))

    def market_close(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, close_percent: str = None):
        symbol = self.parse_symbol(base, quote)
        quote = self.parse_quote(quote)
        side = self.parse_side(side)

        close_amount = self.get_amount(base, quote, amount, close_percent)
        return self.future.create_order(symbol, type.lower(), side, close_amount, params={"reduceOnly": True})

    def set_leverage(self, leverage, symbol, side):
        if side == "entry/buy":
            hold_side = "long"
        elif side == "entry/sell":
            hold_side = "short"
        market = self.future.market(symbol)
        request = {
            "symbol": market["id"],
            "marginCoin": market["settleId"],
            "leverage": leverage,
            # 'holdSide': 'long' or 'short',
        }

        account = self.future.privateMixGetAccountAccount({"symbol": market["id"], "marginCoin": market["settleId"]})
        if account["data"]["marginMode"] == "fixed":
            request |= {"holdSide": hold_side}
        return self.future.privateMixPostAccountSetLeverage(request)

    def fetch_ticker(self, base: str, quote: str):
        if quote.endswith(".P"):
            quote = self.parse_quote(quote)
            symbol = f"{base}/{quote}:{quote}"
            return self.future.fetch_ticker(symbol)
        else:
            symbol = f"{base}/{quote}:{quote}"
            return self.spot.fetch_ticker(symbol)

    def get_amount(self, base, quote, amount, percent) -> float:
        if amount is not None and percent is not None:
            raise Exception("amount와 percent는 동시에 사용할 수 없습니다")
        elif amount is not None:
            result = amount
        elif percent is not None:
            if self.order_info.side in ("buy", "entry/buy", "entry/sell"):
                cash = self.get_futures_balance(quote) * percent/100 if self.order_info.is_crypto and self.order_info.is_futures else self.get_spot_balance(quote) * percent/100
                current_price = self.fetch_price(base, quote)
                result = cash / current_price
                print(result, cash)
            elif self.order_info.side in ("sell", "close/buy", "close/sell"):
                symbol = self.parse_symbol(base, quote)
                free_amount = self.get_futures_position(symbol) if self.order_info.is_crypto and self.order_info.is_futures else self.get_spot_balance(base)
                result = free_amount * float(percent)/100
        else:
            raise Exception("amount와 percent 중 하나는 입력해야 합니다")
        return result

    def get_spot_balance(self, base) -> float:
        balance = (self.spot.fetch_free_balance({"coin": base})).get(base)
        if balance is None or balance == 0:
            raise Exception("거래할 수량이 없습니다")
        return balance

    def get_futures_balance(self, base) -> float:
        balance = (self.future.fetch_free_balance({"coin": base})).get(base)
        if balance is None or balance == 0:
            raise Exception("거래할 수량이 없습니다")
        return balance

    def get_futures_position(self, symbol):
        position = self.future.fetch_position(symbol)
        if position:
            contracts = float(position["info"]["available"])
            if contracts == 0:
                raise Exception("포지션이 없습니다")
            else:
                return contracts
        else:
            raise Exception("포지션이 없습니다")

    def fetch_ticker(self, base: str, quote: str):
        symbol = self.parse_symbol(base, quote)
        if self.order_info.is_futures:
            return self.future.fetch_ticker(symbol)
        else:
            return self.spot.fetch_ticker(symbol)

    def fetch_price(self, base: str, quote: str):
        return self.fetch_ticker(base, quote)["last"]
