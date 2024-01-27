from pprint import pprint
from exchange.pexchange import ccxt
from exchange.database import db
from exchange.model import MarketOrder
import exchange.error as error
from devtools import debug


class Bitget:
    def __init__(self, key, secret, passphrase=None):
        self.client = ccxt.bitget(
            {
                "apiKey": key,
                "secret": secret,
                "password": passphrase,
            }
        )
        self.client.load_markets()
        self.order_info: MarketOrder = None
        self.position_mode = "hedge"

    def init_info(self, order_info: MarketOrder):
        self.order_info = order_info

        unified_symbol = order_info.unified_symbol
        market = self.client.market(unified_symbol)

        if order_info.amount is not None:
            order_info.amount = float(
                self.client.amount_to_precision(
                    order_info.unified_symbol, order_info.amount
                )
            )

        if order_info.is_futures:
            if order_info.is_coinm:
                self.client.options["defaultType"] = "delivery"
                is_contract = market.get("contract")
                if is_contract:
                    order_info.is_contract = True
                    order_info.contract_size = market.get("contractSize")
            else:
                self.client.options["defaultType"] = "swap"
        else:
            self.client.options["defaultType"] = "spot"

    def get_ticker(self, symbol: str):
        return self.client.fetch_ticker(symbol)

    def get_price(self, symbol: str):
        return self.get_ticker(symbol)["last"]

    def get_futures_position(self, symbol):
        positions = self.client.fetch_positions([symbol])
        long_contracts = None
        short_contracts = None

        if positions:
            if isinstance(positions, list):
                for position in positions:
                    if position["side"] == "long":
                        long_contracts = float(position["info"]["available"])
                    elif position["side"] == "short":
                        short_contracts = float(position["info"]["available"])

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
                contracts = float(positions["info"]["available"])
                if not contracts:
                    raise error.PositionNoneError()
                else:
                    return contracts
        else:
            raise error.PositionNoneError()

    def get_balance(self, base: str):
        free_balance_by_base = None
        if self.order_info.is_entry or (
            self.order_info.is_spot
            and (self.order_info.is_buy or self.order_info.is_sell)
        ):
            free_balance = (
                self.client.fetch_free_balance({"coin": base})
                if not self.order_info.is_total
                else self.client.fetch_total_balance({"coin": base})
            )
            free_balance_by_base = free_balance.get(base)
        if free_balance_by_base is None or free_balance_by_base == 0:
            raise error.FreeAmountNoneError()
        return free_balance_by_base

    def get_amount(self, order_info: MarketOrder) -> float:
        if order_info.amount is not None and order_info.percent is not None:
            raise error.AmountPercentBothError()
        elif order_info.amount is not None:
            result = order_info.amount

        elif order_info.percent is not None:
            if order_info.is_entry or (order_info.is_spot and order_info.is_buy):
                free_quote = self.get_balance(order_info.quote)
                cash = free_quote * (order_info.percent - 1) / 100
                current_price = self.get_price(order_info.unified_symbol)
                result = cash / current_price
            elif self.order_info.is_close:
                free_amount = self.get_futures_position(order_info.unified_symbol)
                result = free_amount * order_info.percent / 100
            elif order_info.is_spot and order_info.is_sell:
                free_amount = self.get_balance(order_info.base)
                result = free_amount * order_info.percent / 100
            result = float(
                self.client.amount_to_precision(order_info.unified_symbol, result)
            )
            order_info.amount_by_percent = result
        else:
            raise error.AmountPercentNoneError()
        return result

    def set_leverage(self, leverage, symbol):
        if self.order_info.is_buy:
            hold_side = "long"
        elif self.order_info.is_sell:
            hold_side = "short"
        market = self.client.market(symbol)
        request = {
            "symbol": market["id"],
            "marginCoin": market["settleId"],
            "leverage": leverage,
            # 'holdSide': 'long' or 'short',
        }

        account = self.client.privateMixGetAccountAccount(
            {"symbol": market["id"], "marginCoin": market["settleId"]}
        )
        if account["data"]["marginMode"] == "fixed":
            request |= {"holdSide": hold_side}
        return self.client.privateMixPostAccountSetLeverage(request)

    def market_order(self, order_info: MarketOrder):
        from exchange.pexchange import retry

        symbol = order_info.unified_symbol
        params = {}
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
            raise error.OrderError(e, order_info)

    def market_buy(self, order_info: MarketOrder):
        # 비용주문
        buy_amount = self.get_amount(order_info)
        order_info.amount = buy_amount
        order_info.price = self.get_price(order_info.unified_symbol)

        return self.market_order(order_info)

    def market_sell(self, order_info: MarketOrder):
        sell_amount = self.get_amount(order_info)
        order_info.amount = sell_amount
        return self.market_order(order_info)

    def market_entry(self, order_info: MarketOrder):
        from exchange.pexchange import retry

        symbol = order_info.unified_symbol
        entry_amount = self.get_amount(order_info)
        if entry_amount == 0:
            raise error.MinAmountError()
        if self.position_mode == "one-way":
            new_side = order_info.side + "_single"
            params = {"side": new_side}
        elif self.position_mode == "hedge":
            params = {}
        if order_info.leverage is not None:
            self.set_leverage(order_info.leverage, symbol)
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
            raise error.OrderError(e, order_info)

    def market_close(self, order_info: MarketOrder):
        from exchange.pexchange import retry

        symbol = self.order_info.unified_symbol
        close_amount = self.get_amount(order_info)
        if self.position_mode == "one-way":
            new_side = order_info.side + "_single"
            params = {"reduceOnly": True, "side": new_side}
        elif self.position_mode == "hedge":
            params = {"reduceOnly": True}
        try:
            result = retry(
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

            return result
        except Exception as e:
            raise error.OrderError(e, self.order_info)
