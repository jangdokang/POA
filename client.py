import time
import httpx
import asyncio
from exchange import get_exchange as get_ex
from exchange import KoreaInvestment


class Client():
    def __init__(self, base_url="http://127.0.0.1:8000", password="dokang", headers: dict = None):
        self.base_url = base_url
        self.base_headers = headers
        self.base_data = {
            "password": password,
            "type": "market",
        }
        self.session = httpx.Client()
        self.async_session = httpx.AsyncClient()

    def get_exchange(self, exchange: str, kis_number=1):

        ex = get_ex(exchange, kis_number)
        return ex

    def get_binance(self):
        return self.get_exchange("BINANCE").BINANCE

    def get_kis1(self) -> KoreaInvestment:
        return self.get_exchange("KRX", 1)

    def get_kis2(self) -> KoreaInvestment:
        return self.get_exchange("KRX", 2)

    def close_session(self):
        self.session.close()

    def get(self, endpoint: str, params: dict = None, headers: dict = None, as_json=True):
        if as_json:
            return self.session.get(f"{self.base_url}{endpoint}", params=params, headers=headers).json()
        else:
            return self.session.get(f"{self.base_url}{endpoint}", params=params, headers=headers)

    def post(self, endpoint: str, data: dict = None, headers: dict = None, as_json=True):
        if as_json:
            result = self.session.post(f"{self.base_url}{endpoint}", json=data, headers=headers)
            return result.json(), result.headers
        else:
            return self.session.post(f"{self.base_url}{endpoint}", json=data, headers=headers)

    async def aclose_session(self):
        await self.async_session.aclose()

    async def get_async(self, endpoint, params=None, headers=None, as_json=True):
        try:
            if as_json:
                return (await self.async_session.get(f"{self.base_url}{endpoint}", params=params, headers=headers)).json()
            else:
                return (await self.async_session.get(f"{self.base_url}{endpoint}", params=params, headers=headers))
        except asyncio.CancelledError as err:
            return asyncio.CancelledError

    async def post_async(self, endpoint, data, headers=None, as_json=True):
        try:
            if as_json:
                return (await self.async_session.post(f"{self.base_url}{endpoint}", json=data, headers=headers)).json()
            else:
                return (await self.async_session.post(f"{self.base_url}{endpoint}", json=data, headers=headers))
        except asyncio.CancelledError as err:
            return asyncio.CancelledError

    async def get_price_async(self, exchange, base, quote):
        return await self.post_async("/price", {"exchange": exchange, "base": base, "quote": quote})

    def get_price(self, exchange, base, quote):
        return self.post("/price", {"exchange": exchange, "base": base, "quote": quote})

    def buy(self, exchange, base, quote, amount=None, percent=None, kis_number: int = None):
        print("kis_number:", kis_number)
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "buy",
            "amount": amount,
            "percent": percent,
            "kis_number": kis_number
        }
        return self.post("/order", data)

    async def buy_async(self, exchange, base, quote, amount: float = None, percent: float = None, kis_number: int = None):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "buy",
            "amount": amount,
            "percent": percent,
            "kis_number": kis_number
        }
        return await self.post_async("/order", data)

    def buy_by_cost(self, exchange, base, quote, cost=None, percent=None):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "buy",
            "amount": cost,
            "percent": percent,
            "price": 1.0
        }
        return self.post("/order", data)

    async def buy_by_cost_async(self, exchange, base, quote, cost):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "buy",
            "amount": cost,
            "price": 1.0
        }
        return await self.post_async("/order", data)

    def sell(self, exchange, base, quote, amount=None, percent=None, kis_number=None):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "sell",
            "amount": amount,
            "percent": percent,
            "kis_number": kis_number
        }
        return self.post("/order", data)

    async def sell_async(self, exchange, base, quote, amount=None, percent=None, kis_number=None):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "sell",
            "amount": amount,
            "percent": percent,
            "kis_number": kis_number
        }
        return await self.post_async("/order", data)

    def entry(self, exchange, base, quote, amount=None, percent=None, leverage=None, stop_price=None, profit_price=None):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "entry/buy",
            "amount": amount,
            "percent": percent,
            "leverage": leverage,
            "stop_price": stop_price,
            "profit_price": profit_price
        }
        return self.post("/order", data)

    def close(self, exchange, base, quote, amount=None, percent=None):
        data = self.base_data | {
            "exchange": exchange,
            "base": base,
            "quote": quote,
            "side": "close/sell",
            "amount": amount,
            "percent": percent
        }
        return self.post("/order", data)

    def upbit_buy_by_cost(self, base, quote, cost=None, percent=None):
        return self.buy_by_cost("UPBIT", base, quote, cost, percent)

    async def upbit_buy_by_cost_async(self, base, quote, cost):
        return await self.buy_by_cost_async("UPBIT", base, quote, cost)

    def upbit_sell(self, base, quote, amount=None, percent=None):
        self.sell("UPBIT", base, quote, amount, percent)

    def binance_buy(self, base, quote, amount=None, percent=None):
        return self.buy("BINANCE", base, quote, amount, percent)

    async def binance_buy_async(self, base, quote, amount):
        return await self.buy_async("BINANCE", base, quote, amount)

    def binance_sell(self, base, quote, amount=None, percent=None):
        return self.sell("BINANCE", base, quote, amount, percent)

    def binance_entry(self, base, quote, amount=None, percent=None, leverage=None):
        return self.entry("BINANCE", base, quote, amount, percent, leverage)

    def binance_close(self, base, quote, amount=None, percent=None):
        return self.close("BINANCE", base, quote, amount, percent)

    def kis_buy(self, exchange, base, quote, amount, kis_number):
        return self.buy(exchange, base, quote, amount, None, kis_number)

    def kis_sell(self, exchange, base, quote, amount, kis_number):
        return self.sell(exchange, base, quote, amount, None, kis_number)

    def bitget_entry(self, base, quote, amount=None, percent=None, leverage=None):
        return self.entry("BITGET", base, quote, amount, percent, leverage)

    def bitget_close(self, base, quote, amount=None, percent=None):
        return self.close("BITGET", base, quote, amount, percent)

    def bitget_buy_by_cost(self, base, quote, cost=None, percent=None):
        return self.buy_by_cost("BITGET", base, quote, cost, percent)

    def bitget_sell(self, base, quote, amount=None, percent=None):
        return self.sell("BITGET", base, quote, amount, percent)

    def bybit_entry(self, base, quote, amount=None, percent=None, leverage=None):
        return self.entry("BYBIT", base, quote, amount, percent, leverage)

    def bybit_close(self, base, quote, amount=None, percent=None):
        return self.close("BYBIT", base, quote, amount, percent)

    def bybit_buy_by_cost(self, base, quote, cost=None, percent=None):
        return self.buy_by_cost("BYBIT", base, quote, cost, percent)

    def bybit_sell(self, base, quote, amount=None, percent=None):
        return self.sell("BYBIT", base, quote, amount, percent)


async def main():

    start_time = time.perf_counter()
    client = Client()
    # bases = ["BTC", "ETH", "DOGE", "XRP", "EOS", "SOL", "LTC", "MANA", "NEAR", "BNB", "FTT", "BTT", "XLM", "VET"]
    # tasks = []
    # try:
    #     async with asyncio.TaskGroup() as tg:
    #         for base in bases:
    #             tasks.append((f"{base}", tg.create_task(client.get_price_async("BINANCE", base, "USDT"))))
    # except* BaseException as err:
    #     print(f"{err=}")

    # results = [(task[0], task[1].result()) for task in tasks]
    # print(results)
    # end_time = time.perf_counter()
    # print(end_time - start_time)
    await client.aclose_session()


if __name__ == "__main__":
    asyncio.run(main())
