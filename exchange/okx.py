import ccxt
import ccxt.async_support as ccxt_async
from devtools import debug

from exchange.model import MarketOrder
import exchange.error as error


class Okx:
    def __init__(self, key, secret, passphrase):
        self.client = ccxt.okx(
            {
                "apiKey": key,
                "secret": secret,
                "password": passphrase,
            }
        )
        self.client.load_markets()
        self.order_info: MarketOrder = None
        self.position_mode = "one-way"

    def init_info(self, order_info: MarketOrder):
        self.order_info = order_info

        unified_symbol = order_info.unified_symbol
        market = self.client.market(unified_symbol)

        is_contract = market.get("contract")
        if is_contract:
            order_info.is_contract = True
            order_info.contract_size = market.get("contractSize")

        if order_info.is_futures:
            self.client.options["defaultType"] = "swap"
        else:
            self.client.options["defaultType"] = "spot"

    def get_amount_precision(self, symbol):
        market = self.client.market(symbol)
        precision = market.get("precision")
        if precision is not None and isinstance(precision, dict) and "amount" in precision:
            return precision.get("amount")

    def get_contract_size(self, symbol):
        market = self.client.market(symbol)
        debug(market)
        return market.get("contractSize")

    def parse_symbol(self, base: str, quote: str):
        if self.order_info.is_futures:
            return f"{base}/{quote}:{quote}"
        else:
            return f"{base}/{quote}"

    def get_ticker(self, symbol: str):
        return self.client.fetch_ticker(symbol)

    def get_price(self, symbol: str):
        return self.get_ticker(symbol)["last"]

    def get_balance(self, base: str):
        free_balance_by_base = None
        if self.order_info.is_entry or (
            self.order_info.is_spot and (self.order_info.is_buy or self.order_info.is_sell)
        ):
            free_balance = self.client.fetch_free_balance()
            free_balance_by_base = free_balance.get(base)

        if free_balance_by_base is None or free_balance_by_base == 0:
            raise error.FreeAmountNoneError()
        return free_balance_by_base

    def get_futures_position(self, symbol=None, all=False):
        if symbol is None and all:
            positions = self.client.fetch_balance()["info"]["positions"]
            positions = [position for position in positions if float(position["positionAmt"]) != 0]
            return positions

        positions = self.client.fetch_positions([symbol])
        long_contracts = None
        short_contracts = None
        if positions:
            for position in positions:
                if position["side"] == "long":
                    long_contracts = position["contracts"]
                elif position["side"] == "short":
                    short_contracts = position["contracts"]

            if self.order_info.is_close and self.order_info.is_buy:
                if not short_contracts:
                    raise error.ShortPositionNoneError()
                else:
                    return short_contracts
            elif self.order_info.is_close and self.order_info.is_sell:
                if not long_contracts:
                    raise error.LongPositionNoneError()
                else:
                    return long_contracts
        else:
            raise error.PositionNoneError()

    def get_amount(self, order_info: MarketOrder) -> float:
        if order_info.amount is not None and order_info.percent is not None:
            raise error.AmountPercentBothError()
        elif order_info.amount is not None:
            if order_info.is_contract:
                result = order_info.amount // order_info.contract_size
            else:
                result = order_info.amount
        elif order_info.percent is not None:
            if self.order_info.is_entry or (order_info.is_spot and order_info.is_buy):
                if order_info.is_coinm:
                    free_base = self.get_balance(order_info.base)
                    if order_info.is_contract:
                        result = (free_base * order_info.percent / 100) // order_info.contract_size
                    else:
                        result = free_base * order_info.percent / 100
                else:
                    free_quote = self.get_balance(order_info.quote)
                    cash = free_quote * order_info.percent / 100
                    current_price = self.get_price(order_info.unified_symbol)
                    if order_info.is_contract:
                        result = (cash / current_price) // order_info.contract_size
                    else:
                        result = cash / current_price
            elif self.order_info.is_close:
                if order_info.is_contract:
                    free_amount = self.get_futures_position(order_info.unified_symbol)
                    result = free_amount * order_info.percent / 100
                else:
                    free_amount = self.get_futures_position(order_info.unified_symbol)
                    result = free_amount * float(order_info.percent) / 100

            elif order_info.is_spot and order_info.is_sell:
                free_amount = self.get_balance(order_info.base)
                result = free_amount * float(order_info.percent) / 100

            result = float(self.client.amount_to_precision(order_info.unified_symbol, result))
            order_info.amount_by_percent = result
        else:
            raise error.AmountPercentNoneError()

        return result

    def market_order(self, order_info: MarketOrder):
        from exchange.pexchange import retry

        symbol = order_info.unified_symbol  # self.parse_symbol(order_info.base, order_info.quote)
        params = {"tgtCcy": "base_ccy"}

        try:
            return retry(
                self.client.create_order,
                symbol,
                order_info.type.lower(),
                order_info.side,
                order_info.amount,
                order_info.price,
                params,
                order_info=order_info,
                max_attempts=5,
                delay=0.1,
                instance=self,
            )
        except Exception as e:
            raise error.OrderError(e, self.order_info)

    def market_buy(
        self,
        order_info: MarketOrder,
    ):
        # 수량기반
        buy_amount = self.get_amount(order_info)
        fee = self.client.fetch_trading_fee(self.order_info.unified_symbol)
        order_info.amount = buy_amount
        result = self.market_order(order_info)
        order_info.amount = buy_amount * (1 - fee["taker"])
        return result

    def market_sell(
        self,
        order_info: MarketOrder,
    ):
        # 수량기반
        symbol = order_info.unified_symbol  # self.parse_symbol(order_info.base, order_info.quote)
        fee = self.client.fetch_trading_fee(symbol)
        sell_amount = self.get_amount(order_info)

        if order_info.percent is not None:
            order_info.amount = sell_amount
        else:
            order_info.amount = sell_amount * (1 - fee["taker"])

        return self.market_order(order_info)

    def set_leverage(self, leverage, symbol):
        if self.order_info.is_futures:
            if self.order_info.is_futures and self.order_info.is_entry:
                if self.order_info.is_buy:
                    pos_side = "long"
                elif self.order_info.is_sell:
                    pos_side = "short"
            try:
                if self.order_info.margin_mode is None or self.order_info.margin_mode == "isolated":
                    if self.position_mode == "hedge":
                        self.client.set_leverage(leverage, symbol, params={"mgnMode": "isolated", "posSide": pos_side})
                    elif self.position_mode == "one-way":
                        self.client.set_leverage(leverage, symbol, params={"mgnMode": "isolated", "posSide": "net"})
                else:
                    self.client.set_leverage(leverage, symbol, params={"mgnMode": self.order_info.margin_mode})
            except Exception as e:
                pass

    def market_entry(
        self,
        order_info: MarketOrder,
    ):
        from exchange.pexchange import retry

        symbol = order_info.unified_symbol  # self.parse_symbol(order_info.base, order_info.quote)

        entry_amount = self.get_amount(order_info)
        if entry_amount == 0:
            raise error.MinAmountError()

        params = {}
        if order_info.leverage is None:
            self.set_leverage(1, symbol)
        else:
            self.set_leverage(order_info.leverage, symbol)
        if order_info.margin_mode is None:
            params |= {"tdMode": "isolated"}
        else:
            params |= {"tdMode": order_info.margin_mode}

        if self.position_mode == "one-way":
            params |= {}
        elif self.position_mode == "hedge":
            if order_info.is_futures and order_info.side == "buy":
                if order_info.is_entry:
                    pos_side = "long"
                elif order_info.is_close:
                    pos_side = "short"
            elif order_info.is_futures and order_info.side == "sell":
                if order_info.is_entry:
                    pos_side = "short"
                elif order_info.is_close:
                    pos_side = "long"
            params |= {"posSide": pos_side}

        try:
            return retry(
                self.client.create_order,
                symbol,
                order_info.type.lower(),
                order_info.side,
                abs(entry_amount),
                None,
                params,
                order_info=order_info,
                max_attempts=5,
                delay=0.1,
                instance=self,
            )
        except Exception as e:
            raise error.OrderError(e, self.order_info)

    def market_close(
        self,
        order_info: MarketOrder,
    ):
        from exchange.pexchange import retry

        symbol = self.order_info.unified_symbol
        close_amount = self.get_amount(order_info)

        if self.position_mode == "one-way":
            if self.order_info.margin_mode is None or self.order_info.margin_mode == "isolated":
                params = {"reduceOnly": True, "tdMode": "isolated"}
            elif self.order_info.margin_mode == "cross":
                params = {"reduceOnly": True, "tdMode": "cross"}

        elif self.position_mode == "hedge":
            if order_info.is_futures and order_info.side == "buy":
                if order_info.is_entry:
                    pos_side = "long"
                elif order_info.is_close:
                    pos_side = "short"
            elif order_info.is_futures and order_info.side == "sell":
                if order_info.is_entry:
                    pos_side = "short"
                elif order_info.is_close:
                    pos_side = "long"
            if self.order_info.margin_mode is None or self.order_info.margin_mode == "isolated":
                params = {"posSide": pos_side, "tdMode": "isolated"}
            elif self.order_info.margin_mode == "cross":
                params = {"posSide": pos_side, "tdMode": "cross"}

        try:
            return retry(
                self.client.create_order,
                symbol,
                order_info.type.lower(),
                order_info.side,
                abs(close_amount),
                None,
                params,
                order_info=order_info,
                max_attempts=5,
                delay=0.1,
                instance=self,
            )
        except Exception as e:
            raise error.OrderError(e, self.order_info)
