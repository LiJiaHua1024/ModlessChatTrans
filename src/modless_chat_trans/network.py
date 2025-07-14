#!/usr/bin/env python3
"""
network.py
~~~~~~~~~~
一个极简的 **Minecraft TCP 代理**：
1. 监听本地端口，等待客户端加入；
2. 每当有客户端连接时，自动再去连接真正的 MC 服务器；
3. 建立两条转发通道：客户端→代理→服务器、服务器→代理→客户端；
4. 在服务器→客户端方向实时解析 *Play* 阶段的「聊天消息」数据包并触发 `callback`。

只关注原版协议中 **未压缩** 的聊天包（packet id 0x0F 或 0x0E，视版本而定）。
若你的服务器开启了压缩或版本不同，可自行拓展 `ChatParser`。
"""

import asyncio
import argparse
import json
from typing import Optional, Tuple, List

# ----------------------------------------- #
#               回调函数                     #
# ----------------------------------------- #
def callback(msg: str):
    """当捕获到聊天消息时被调用"""
    print(f"[*] 检测到聊天消息: {msg}")


# ----------------------------------------- #
#         VarInt 处理与数据包解析            #
# ----------------------------------------- #
def read_varint(buf: bytearray, start: int = 0) -> Tuple[Optional[int], int]:
    """
    尝试从 buf[start:] 读取一个 VarInt。
    返回 (value, new_index)；若数据不足则 (None, start)。
    """
    num_read = 0
    result = 0
    idx = start

    while idx < len(buf):
        byte = buf[idx]
        result |= (byte & 0x7F) << (7 * num_read)
        num_read += 1
        idx += 1

        if num_read > 5:
            raise ValueError("VarInt is too big")

        if (byte & 0x80) == 0:
            return result, idx

    # 数据不足
    return None, start


class ChatParser:
    """
    将服务器->客户端的字节流拼接为完整 MC 数据包，
    识别聊天包并触发 callback。
    """
    CHAT_PACKET_IDS = {0x0F, 0x0E}  # 常见版本 chat packet id

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        """向解析器追加数据，并尝试解析"""
        self.buf.extend(data)
        packets = self._split_packets()
        for p in packets:
            self._handle_packet(p)

    # -------------------- private -------------------- #
    def _split_packets(self) -> List[bytes]:
        """根据 VarInt Length 拆分完整数据包列表"""
        packets = []
        while True:
            # 先读 length
            length, idx = read_varint(self.buf, 0)
            if length is None:
                break  # 长度字节不完整
            # 整个包是否已到齐?
            if len(self.buf) - idx < length:
                break
            # 取出一个完整包
            packet = bytes(self.buf[idx : idx + length])
            packets.append(packet)
            # 从缓冲区中删掉已处理内容
            del self.buf[: idx + length]
        return packets

    def _handle_packet(self, packet: bytes):
        """
        判断是否为聊天消息包：
        packet = VarInt(packet_id) + payload
        play state 下 chat 包结构：
          VarInt packet_id (0x0F/0x0E)
          String JSON      (VarInt len + bytes)
          Byte   position
          (1.19+  UUID) ...
        此处我们只解析第一个 String
        """
        pkt_id, idx = read_varint(bytearray(packet), 0)
        if pkt_id is None:
            return  # 不可能
        if pkt_id not in self.CHAT_PACKET_IDS:
            return  # 非聊天包

        # 读取 JSON 字符串
        msg_len, jdx = read_varint(bytearray(packet), idx)
        if msg_len is None:
            return
        json_bytes = packet[jdx : jdx + msg_len]
        try:
            text_json = json.loads(json_bytes.decode("utf-8"))
            msg = self._extract_text(text_json)
            if msg:
                callback(msg)
        except Exception:
            # 解码失败，无视
            pass

    @staticmethod
    def _extract_text(obj) -> str:
        """
        Minecraft 的聊天 JSON 可能嵌套 'text', 'extra' 等结构。
        这里做一个尽量通用但很简短的提取。
        """
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            pieces = []
            if "text" in obj:
                pieces.append(obj["text"])
            if "extra" in obj and isinstance(obj["extra"], list):
                for e in obj["extra"]:
                    pieces.append(ChatParser._extract_text(e))
            return "".join(pieces)
        if isinstance(obj, list):
            return "".join(ChatParser._extract_text(i) for i in obj)
        return ""


# ----------------------------------------- #
#           连接/转发逻辑 (asyncio)          #
# ----------------------------------------- #
class ProxyServer:
    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        remote_host: str,
        remote_port: int,
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.chat_parser = ChatParser()  # 每个连接实例化新的

    async def start(self):
        server = await asyncio.start_server(
            self._handle_client, self.listen_host, self.listen_port
        )
        addr = server.sockets[0].getsockname()
        print(f"[+] 代理已启动，监听 {addr}")
        async with server:
            await server.serve_forever()

    # -------------------- private -------------------- #
    async def _handle_client(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ):
        peer = client_writer.get_extra_info("peername")
        print(f"[+] 客户端 {peer} 已连接，正在连接真实服务器 ...")
        try:
            server_reader, server_writer = await asyncio.open_connection(
                self.remote_host, self.remote_port
            )
        except Exception as e:
            print(f"[!] 无法连接到真实服务器: {e}")
            client_writer.close()
            await client_writer.wait_closed()
            return

        print(f"[+] 已建立 {peer} <-> ({self.remote_host},{self.remote_port})")

        async def bridge(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            direction: str,
            parser: Optional[ChatParser] = None,
        ):
            try:
                while not reader.at_eof():
                    data = await reader.read(4096)
                    if not data:
                        break
                    if parser:  # 服务器->客户端方向需要解析
                        parser.feed(data)
                    writer.write(data)
                    await writer.drain()
            except Exception as e:
                # 打印错误但继续执行关闭
                print(f"[!] 转发异常({direction}): {e}")
            finally:
                writer.close()

        # 两条流水线：client->server 与 server->client
        await asyncio.gather(
            bridge(client_reader, server_writer, "C->S"),
            bridge(server_reader, client_writer, "S->C", self.chat_parser),
        )
        print(f"[-] 连接 {peer} 已关闭")


# ----------------------------------------- #
#                 main 入口                 #
# ----------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Minecraft 聊天抓取代理")
    parser.add_argument(
        "--listen-host", default="0.0.0.0", help="代理监听地址 (默认 0.0.0.0)"
    )
    parser.add_argument(
        "--listen-port", type=int, default=25566, help="代理监听端口 (默认 25566)"
    )
    parser.add_argument(
        "--remote-host", required=True, help="真实 MC 服务器地址/IP"
    )
    parser.add_argument(
        "--remote-port", type=int, default=25565, help="真实 MC 服务器端口 (默认 25565)"
    )
    args = parser.parse_args()

    proxy = ProxyServer(
        args.listen_host, args.listen_port, args.remote_host, args.remote_port
    )
    try:
        asyncio.run(proxy.start())
    except KeyboardInterrupt:
        print("\n[+] 已退出")


if __name__ == "__main__":
    main()

# # 整个程序的执行：
# # 1. 启动代理服务器，监听端口，等待客户端连接。
# # 2. 当有客户端连接时，连接真实的 MC 服务器。
# # 3. 其实就是转发消息，分别处理 客户端->代理->服务器 和 服务器->代理->客户端 的数据转发。
# # 4. 转发的同时，识别每一个转发的数据包。 如果是聊天消息，数据包则提取聊天消息并 callback。
# #
# # Callback函数已经提供，需要做的只有上面四步。
# def callback(msg):
#     print(f"[*] 检测到聊天消息: {msg}")
# # def __init__(self, callback, dst_ip, dst_port)
#
# import socket
# import threading
# import struct
# import time
#
#
# # ========================
# # 辅助函数：VarInt 编解码
# # ========================
# def read_varint(sock):
#     """
#     从 sock 中读取一个 VarInt 并返回 (varint_value, bytes_consumed)，
#     如果读取失败则返回 (None, 0)。
#     """
#     shift = 0
#     result = 0
#     bytes_consumed = 0
#     while True:
#         byte = sock.recv(1)
#         if not byte:
#             return None, 0  # 连接被断开或读不到数据
#         byte_val = byte[0]
#         result |= (byte_val & 0x7F) << shift
#         shift += 7
#         bytes_consumed += 1
#         if (byte_val & 0x80) == 0:
#             break
#         if bytes_consumed > 5:
#             # VarInt 不应超过 5 字节
#             raise ValueError("VarInt is too big.")
#     return result, bytes_consumed
#
#
# def write_varint(value):
#     """
#     将整数 value 编码为 VarInt 格式的 bytes。
#     """
#     out = b""
#     while True:
#         temp = value & 0x7F
#         value >>= 7
#         if value != 0:
#             out += struct.pack("B", temp | 0x80)
#         else:
#             out += struct.pack("B", temp)
#             break
#     return out
#
#
# # ========================
# # 核心代理类
# # ========================
# class MinecraftProxy:
#     """
#     简易版本的 Minecraft 1.8 协议代理。
#
#     :param callback: 外部提供的消息回调函数 (str) -> str
#     :param dst_ip:   真实目标服务器 IP
#     :param dst_port: 真实目标服务器端口
#     :param listen_ip: 代理服务器监听 IP（默认 0.0.0.0）
#     :param listen_port: 代理服务器监听端口（默认 25566）
#     """
#
#     def __init__(self, callback, dst_ip, dst_port, listen_ip="0.0.0.0", listen_port=25566):
#         self.callback = callback
#         self.dst_ip = dst_ip
#         self.dst_port = dst_port
#         self.listen_ip = listen_ip
#         self.listen_port = listen_port
#         self.server_socket = None
#         self.running = False
#
#     def start(self):
#         """
#         启动代理服务器，等待 Minecraft 客户端连接。
#         """
#         self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         self.server_socket.bind((self.listen_ip, self.listen_port))
#         self.server_socket.listen(5)
#
#         print(f"[Proxy] 代理服务器已启动，监听地址: {self.listen_ip}:{self.listen_port}")
#
#         self.running = True
#         while self.running:
#             try:
#                 client_sock, addr = self.server_socket.accept()
#                 print(f"[Proxy] 收到来自 {addr} 的连接。")
#                 # 为每个客户端起一个线程去处理
#                 threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
#             except Exception as e:
#                 print("[Proxy] 异常：", e)
#                 break
#
#     def stop(self):
#         """
#         停止代理服务器。
#         """
#         self.running = False
#         if self.server_socket:
#             self.server_socket.close()
#             self.server_socket = None
#         print("[Proxy] 代理服务器已停止。")
#
#     def handle_client(self, client_sock):
#         """
#         处理单个 Minecraft 客户端连接：
#         1. 连接到真实服务器
#         2. 分别开启线程转发数据 (client->server) 和 (server->client)
#         """
#         server_sock = None
#         try:
#             server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             server_sock.connect((self.dst_ip, self.dst_port))
#             print(f"[Proxy] 已连接到真实服务器 {self.dst_ip}:{self.dst_port}")
#
#             # 启动转发线程
#             t1 = threading.Thread(target=self.forward_c2s, args=(client_sock, server_sock), daemon=True)
#             t2 = threading.Thread(target=self.forward_s2c, args=(server_sock, client_sock), daemon=True)
#             t1.start()
#             t2.start()
#
#             # 等待这两个转发线程结束（若任一结束则表示有连接断开）
#             t1.join()
#             t2.join()
#
#         except Exception as e:
#             print("[Proxy] 处理客户端时出现异常:", e)
#         finally:
#             if server_sock:
#                 server_sock.close()
#             client_sock.close()
#             print("[Proxy] 客户端连接已关闭。")
#
#     def forward_c2s(self, src_sock, dst_sock):
#         """
#         负责把客户端发往服务器的数据进行拦截并转发。
#         检查是否为聊天消息包 (ID=0x01 in 1.8, client->server) 并调用 callback。
#         """
#         while True:
#             # 先尝试读取一个包长度（VarInt）
#             length_data = self.safe_peek_varint(src_sock)
#             if not length_data:
#                 break
#             packet_len, _ = length_data
#
#             full_packet = self.safe_recv(src_sock, packet_len)
#             if not full_packet:
#                 break
#
#             # 解包：先读出包ID
#             packet_id, id_size = self.read_packet_id(full_packet)
#             packet_payload = full_packet[id_size:]
#
#             # 判断是否聊天消息包 (客户端->服务器 1.8: 0x01)
#             # 具体可参考 https://wiki.vg/index.php?title=Protocol&oldid=6007
#             if packet_id == 0x01:
#                 # 解析聊天字符串
#                 # 先读 VarInt: 聊天字符串长度
#                 msg_str_len, size_used = self.read_varint_from_bytes(packet_payload)
#                 chat_msg = packet_payload[size_used:size_used + msg_str_len].decode(errors='ignore')
#
#                 # 使用回调替换消息
#                 new_chat_msg = self.callback(chat_msg)
#                 if not isinstance(new_chat_msg, str):
#                     new_chat_msg = chat_msg  # fallback
#
#                 new_chat_bytes = new_chat_msg.encode()
#                 # 重新组装
#                 new_payload = b""
#                 # 写 VarInt(字符串长度)
#                 new_payload += write_varint(len(new_chat_bytes))
#                 # 写消息
#                 new_payload += new_chat_bytes
#
#                 # 包头：VarInt(包ID=0x01)
#                 new_packet_id_bytes = write_varint(0x01)
#                 # 新的完整 payload
#                 new_full_packet = new_packet_id_bytes + new_payload
#
#                 # 外层要再加 VarInt(包总长度)
#                 new_length_bytes = write_varint(len(new_full_packet))
#                 final_data = new_length_bytes + new_full_packet
#
#                 # 转发给服务器
#                 dst_sock.sendall(final_data)
#             else:
#                 # 非聊天包，原封不动转发
#                 # 要把前面读出来的 length + packet 一起发
#                 length_prefix = write_varint(packet_len)
#                 dst_sock.sendall(length_prefix + full_packet)
#
#     def forward_s2c(self, src_sock, dst_sock):
#         """
#         负责把服务器发往客户端的数据进行拦截并转发。
#         检查是否为聊天消息包 (服务器->客户端 1.8: 0x02) 并调用 callback。
#         """
#         while True:
#             length_data = self.safe_peek_varint(src_sock)
#             if not length_data:
#                 break
#             packet_len, _ = length_data
#
#             full_packet = self.safe_recv(src_sock, packet_len)
#             if not full_packet:
#                 break
#
#             # 解包：先读出包ID
#             packet_id, id_size = self.read_packet_id(full_packet)
#             packet_payload = full_packet[id_size:]
#
#             # 判断是否聊天消息包 (服务器->客户端 1.8: 0x02)
#             if packet_id == 0x02:
#                 # 解析 JSON 格式的聊天字符串
#                 msg_str_len, size_used = self.read_varint_from_bytes(packet_payload)
#                 json_str = packet_payload[size_used:size_used + msg_str_len].decode(errors='ignore')
#
#                 # 调用 callback，这里演示只提取并替换“纯文本”部分
#                 # 如果想更精细地修改，可以解析 JSON 结构
#                 new_json_str = self.callback(json_str)
#                 if not isinstance(new_json_str, str):
#                     new_json_str = json_str  # fallback
#
#                 new_json_bytes = new_json_str.encode()
#                 # 重新组装
#                 new_payload = b""
#                 # 写 VarInt(JSON字符串长度)
#                 new_payload += write_varint(len(new_json_bytes))
#                 # 写 JSON
#                 new_payload += new_json_bytes
#
#                 # 后面一般还会有一个 Byte: position(0=chat,1=system,2=game_info)
#                 # 如果当前 payload 还没读完，说明后续字节就是 position
#                 remain_payload = packet_payload[size_used + msg_str_len:]
#                 new_payload += remain_payload
#
#                 # 包头：VarInt(包ID=0x02)
#                 new_packet_id_bytes = write_varint(0x02)
#                 new_full_packet = new_packet_id_bytes + new_payload
#
#                 # 外层再加 VarInt(包总长度)
#                 new_length_bytes = write_varint(len(new_full_packet))
#                 final_data = new_length_bytes + new_full_packet
#
#                 # 转发给客户端
#                 dst_sock.sendall(final_data)
#             else:
#                 # 非聊天包，原封不动转发
#                 length_prefix = write_varint(packet_len)
#                 dst_sock.sendall(length_prefix + full_packet)
#
#     # =========================================
#     # 以下是一些安全读写与字节处理的辅助方法
#     # =========================================
#     def safe_peek_varint(self, sock):
#         """
#         尝试从 sock 中读取一个完整的 VarInt (代表后面包长)，
#         如果 sock 中暂时没有足够数据，可能会阻塞或直接返回 None。
#         """
#         sock.setblocking(False)
#         buf = b""
#         try:
#             # 最多读 5 字节 (VarInt 最大长度)
#             for _ in range(5):
#                 b1 = sock.recv(1)
#                 if not b1:
#                     # 对端关闭
#                     sock.setblocking(True)
#                     return None
#                 buf += b1
#                 if (b1[0] & 0x80) == 0:
#                     break
#         except BlockingIOError:
#             # 没读到足够数据
#             sock.setblocking(True)
#             # 要么睡眠片刻再试，要么直接 None
#             time.sleep(0.01)
#             return None
#         sock.setblocking(True)
#
#         # 解析 VarInt
#         try:
#             length_val, _ = self.read_varint_from_bytes(buf)
#             return length_val, buf.__len__()
#         except:
#             return None
#
#     def safe_recv(self, sock, size):
#         """
#         尝试从 sock 读取 size 字节，如果对端断开或读取不足则返回 None。
#         """
#         buf = b""
#         while len(buf) < size:
#             chunk = sock.recv(size - len(buf))
#             if not chunk:
#                 return None
#             buf += chunk
#         return buf
#
#     def read_packet_id(self, data):
#         """
#         从 data (已去除长度前缀) 的开头读出 packet_id (VarInt)，
#         返回 (packet_id, used_bytes)。
#         """
#         pid_val, used = self.read_varint_from_bytes(data)
#         return pid_val, used
#
#     def read_varint_from_bytes(self, data):
#         """
#         从给定 bytes 中解析出一个 VarInt。
#         返回 (value, bytes_used)。
#         """
#         shift = 0
#         result = 0
#         bytes_used = 0
#         for i, b in enumerate(data):
#             val = b & 0x7F
#             result |= val << shift
#             shift += 7
#             bytes_used += 1
#             if (b & 0x80) == 0:
#                 break
#             if bytes_used > 5:
#                 raise ValueError("VarInt is too big.")
#         return result, bytes_used
#
#
# # ==============
# # 回调示例函数
# # ==============
# def callback(message):
#     """
#     这里仅作示例，无论收到什么文本，都返回固定字符串。
#     """
#     return "this is a test message, if you see it, please let me know (reply with a smiley face). thx :) have a nice day!"
#
#
# # =========================
# # 程序入口：启动代理示例
# # =========================
# if __name__ == '__main__':
#     # 目标服务器 (仅示例, 真正连 Hypixel 需要加密等额外实现)
#     target_ip = 'mc.hypixel.net'
#     target_port = 25565
#
#     # 启动代理
#     proxy = MinecraftProxy(callback, target_ip, target_port, listen_port=25567)
#     try:
#         proxy.start()
#     except KeyboardInterrupt:
#         print("[Main] 检测到 Ctrl+C，准备退出。")
#     finally:
#         proxy.stop()
#
