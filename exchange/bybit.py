from pprint import pprint
from exchange.pexchange import ccxt
from model import MarketOrder
import time

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

    def get_order_amount(self, order_id: str, parsed_symbol: str):
        order_amount = None
        for i in range(8):
            try:
                if self.order_info.is_futures:
                    order_result = self.future.fetch_order(order_id, parsed_symbol)
                else:
                    order_result = self.spot.fetch_order(order_id)
                order_amount = order_result["amount"]
            except Exception as e:
                print("...")
                time.sleep(0.5)
        return order_amount

    def market_order(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None):
        symbol = self.parse_symbol(base, quote)
        order_result = self.spot.create_order(symbol, type.lower(), side.lower(), amount, price)
        return order_result

    def market_buy(self, base: str, quote: str, type: str, side: str, amount: float, price: float = None, buy_percent: float = None):
        # 비용주문
        buy_amount = self.get_amount(base, quote, amount, buy_percent)
        if price is None:
            price = self.fetch_price(base, quote)
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
            order_result = self.future.create_order(symbol, type.lower(), side, abs(entry_amount), params={"position_idx": 0})
            order_amount = self.get_order_amount(order_result["id"], symbol)
            order_result["amount"] = order_amount
            return order_result
        except Exception as e:
            error = str(e)
            if "position idx not match position mode" in error:
                position_idx = None
                if side == "buy":
                    position_idx = 1
                elif side == "sell":
                    position_idx = 2
                if position_idx is None:
                    raise Exception("position_idx error")
                order_result = self.future.create_order(symbol, type.lower(), side, abs(entry_amount), params={"position_idx": position_idx})
                order_amount = self.get_order_amount(order_result["id"], symbol)
                order_result["amount"] = order_amount
                return order_result
            else:
                raise Exception("create_order error")

    def market_close(self, base: str, quote: str, type: str, side: str, amount: float = None, price: float = None, close_percent: str = None):
        symbol = self.parse_symbol(base, quote)
        quote = self.parse_quote(quote)
        side = self.parse_side(side)
        close_amount = self.get_amount(base, quote, amount, close_percent)
        try:
            order_result = self.future.create_order(symbol, type.lower(), side, close_amount, params={"reduceOnly": True, "position_idx": 0})
            order_amount = self.get_order_amount(order_result["id"], symbol)
            order_result["amount"] = order_amount
            return order_result
        except Exception as e:
            error = str(e)
            if "position idx not match position mode" in error:
                position_idx = None
                if side == "buy":
                    position_idx = 2
                elif side == "sell":
                    position_idx = 1
                if position_idx is None:
                    raise Exception("position_idx error")
                order_result = self.future.create_order(symbol, type.lower(), side, abs(close_amount), params={"reduceOnly": True,"positionIdx": position_idx})
                order_amount = self.get_order_amount(order_result["id"], symbol)
                order_result["amount"] = order_amount
                return order_result


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
        positions = self.future.fetch_positions(symbols=[symbol])
        long_contracts = None
        short_contracts = None
        if positions:
            for position in positions:
                if position["side"] == "long":
                    long_contracts = position["contracts"]
                elif position["side"] == "short":
                    short_contracts = position["contracts"]

            if self.order_info.side == "close/buy":
                if not short_contracts:
                    raise Exception("숏 포지션이 없습니다")
                else:
                    return short_contracts
            elif self.order_info.side == "close/sell":
                if not long_contracts:
                    raise Exception("롱 포지션이 없습니다")
                else:
                    return long_contracts
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
