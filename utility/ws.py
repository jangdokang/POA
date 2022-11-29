# from toolbox import Client

from client import Client
import websocket
import _thread
import time
import rel
import json
from pprint import pprint


class Websocket:

    def __init__(self):
        self.client = Client()
        self.binance = self.client.get_binance()
        self.listen_key = self.binance.get_listen_key()
        self.ws_url = f"wss://fstream.binance.com/ws/{self.listen_key}"

    def on_message(self, ws, message):

        datas: dict = json.loads(message)
        event = datas.get("e")
        event_time = datas.get("E")
        transaction_time = datas.get("T")
        cross_wallt_balance = datas.get("cw")
        order = datas.get("o")

        if event == "listenKeyExpired":
            print("Listen key expired")
            self.listen_key = self.binance.get_listen_key()
        elif event == "ORDER_TRADE_UPDATE":
            order_type = order.get("ot")  # TAKE_PROFIT_MARKET, STOP_MARKET
            order_status = order.get("X")  # 새로운 주문은 NEW
            if order_type in ("TAKE_PROFIT_MARKET", "STOP_MARKET"):
                order_id = order.get("i")  # 주문 ID
                client_order_id = order.get("c")  # 주문 고유 ID
                order_symbol = order.get("s")  # 주문 심볼
                order_price = order.get("sp")  # 스탑 가격
                order_side = order.get("S")  # 주문 종류
                order_qty = order.get("q")  # 주문 수량

                print(f"{order_symbol=}, {order_price=}, {order_type=}, {order_status=}, {order_id=}, {client_order_id=}")

            print("=====끝=====")

    def on_error(self, ws, error):
        print(error)

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")

    def on_open(self, ws):
        print("Opened connection")

    def start(self):
        ws = websocket.WebSocketApp(self.ws_url,
                                    on_open=self.on_open,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)

        ws.run_forever(dispatcher=rel, reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
        rel.signal(2, rel.abort)  # Keyboard Interrupt
        rel.dispatch()


if __name__ == "__main__":
    ws = Websocket()
    ws.start()
