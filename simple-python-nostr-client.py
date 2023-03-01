import json
import threading
import time
import uuid

import websocket

client_uuid = uuid.uuid1()


class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.ws = websocket.WebSocketApp(url,
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.caches = {}
        self.messages = []
        self.lock = threading.Lock()
        self.connected = False
        self.stop_flag = False

    def on_open(self, ws):
        print("Connection established")
        self.connected = True

    def on_message(self, ws, message):
        with self.lock:
            if "EOSE" in message or 'too many concurrent REQs' in message or message is None:
                return
            data = json.loads(message)
            pubkey = data[2]["pubkey"]
            try:
                _ = json.loads(data[2]['content'])
                data[2]['content'] = _
                if pubkey in self.caches:
                    self.messages.append({"post": self.caches[pubkey], "user": data})
                    del self.caches[pubkey]
            except Exception as e:
                self.send(self.get_query_user_req(pubkey))
                self.caches.update({pubkey: data})

    def on_error(self, ws, error):
        print("WebSocket error:", error)

    def on_close(self, ws, close_status, close_reason):
        print("Connection closed")
        self.connected = False

    def send(self, message):
        self.ws.send(message)

    def send_periodic_messages(self, message, interval):
        while not self.stop_flag:
            self.send(message)
            time.sleep(interval)

    def get_messages(self):
        with self.lock:
            messages = self.messages[:]
            self.messages.clear()
        return messages

    def stop(self):
        self.stop_flag = True
        self.ws.close()

    def run_forever(self):
        self.ws.run_forever()

    def get_posts_req(self):
        return json.dumps(["REQ", "irc-" + str(client_uuid), {
            "kinds": [1, 6], "limit": 1
        }])

    def get_query_user_req(self, pubkey):
        return json.dumps(["REQ", "nip05-" + pubkey[:8], {
            "kinds": [0], "authors": [pubkey]
        }])


if __name__ == "__main__":
    url = "wss://nostr.wine/"
    client = WebSocketClient(url)

    # 启动WebSocket客户端
    threading.Thread(target=client.run_forever, daemon=True).start()

    # 等待WebSocket连接成功
    while not client.connected:
        time.sleep(0.1)

    # 发送一条消息
    # client.send("Hello, World!")

    # 每5秒发送一次消息
    posts_req = client.get_posts_req()
    threading.Thread(target=client.send_periodic_messages, args=(posts_req, 30), daemon=True).start()

    try:
        # 读取接收到的所有消息
        while True:
            messages = client.get_messages()
            if len(messages) > 0:
                print("Received messages:", messages)
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        # 关闭WebSocket连接
        client.stop()
