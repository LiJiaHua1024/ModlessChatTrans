import socket
import threading
import sys
import ctypes
import ipaddress
import os
import atexit
from modless_chat_trans.interface import CTkMessagebox
from packet_processor import is_chat_packet, decode_varint


def is_admin():
    """
    检查当前程序是否以管理员权限运行

    :return: 是否为管理员的布尔值
    """

    if os.name == "nt":  # Windows
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except OSError:
            return False
    elif os.name == "posix":  # Linux
        return os.geteuid() == 0


def run_as_admin():
    """
    以管理员权限重启程序
    """

    if os.name == "nt":  # Windows
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    elif os.name == "posix":  # Linux
        os.execvp("sudo", ["sudo"] + [sys.executable] + sys.argv)
    sys.exit(0)


def is_domain(host):
    """
    判断主机名是否为域名

    :param host: 要判断的主机名
    :return: 是否为域名的布尔值
    """

    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def modify_hosts(action, domain=None, ip=None):
    """
    修改 hosts 文件，添加指定的域名和 IP 地址映射

    :param action: 指定的操作类型，"add"表示添加，"remove"表示移除
    :param domain: 要添加的域名
    :param ip: 要添加的 IP 地址
    """

    if os.name == "nt":
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
    elif os.name == "posix":
        hosts_path = "/etc/hosts"
    else:
        hosts_path = "/etc/hosts"

    entry = f"{ip} {domain} #Modless Chat Trans proxy\n"

    if action == "add":
        with open(hosts_path, "a+") as hosts_file:
            content = hosts_file.read()
            if entry.strip() not in content:
                hosts_file.write(entry)
        return True
    elif action == "remove":
        with open(hosts_path, "r") as hosts_file:
            content = hosts_file.readlines()
        with open(hosts_path, "w") as hosts_file:
            for line in content:
                if "#Modless Chat Trans proxy" not in line:
                    hosts_file.write(line)
    else:
        raise ValueError("Invalid action. Use 'add' or 'remove'.")


def flush_dns():
    os.system("ipconfig /flushdns")


def transfer_data(source, destination, direction, callback):
    """
    在源套接字和目标套接字之间传输数据

    :param source: 源套接字对象，用于接收数据
    :param destination: 目标套接字对象，用于发送数据
    :param direction: 数据传输方向，"s2c"表示服务器到客户端，"c2s"表示客户端到服务器
    :param callback: 当数据包为聊天数据时调用的回调函数
    """

    buffer = b""
    try:
        while True:
            data = source.recv(4096)
            if not data:
                break

            buffer += data

            while buffer:
                try:
                    packet_length, varint_length = decode_varint(buffer)
                    total_length = packet_length + varint_length

                    if len(buffer) < total_length:
                        break  # 数据不完整，等待更多数据

                    packet = buffer[:total_length]
                    buffer = buffer[total_length:]

                    if is_chat_packet(packet):
                        if direction == "s2c":
                            packet = callback(packet, direction="s2c") or packet
                        elif direction == "c2s":
                            packet = callback(packet, direction="c2s")

                    destination.send(packet)
                    print(f"{direction} 转发: {len(packet)} 字节")
                except Exception as e:
                    print(f"处理数据包时出错: {e}")
                    buffer = buffer[1:]  # 丢弃一个字节并继续
    except Exception as e:
        print(f"{direction} 转发错误: {e}")
    finally:
        source.close()


def handle_client(client_socket, remote_host, remote_port):
    """
    处理客户端连接，建立与远程服务器的连接，并在两者之间传输数据

    :param client_socket: 与客户端连接的套接字对象
    :param remote_host: 远程服务器的主机名或IP地址
    :param remote_port: 远程服务器的端口号
    """

    # print(f"尝试连接到 {remote_host}:{remote_port}")
    try:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(30)
        remote_socket.connect((remote_host, remote_port))
        print(f"成功连接到 {remote_host}:{remote_port}")

        client_to_remote = threading.Thread(target=transfer_data,
                                            args=(client_socket, remote_socket, "客户端 -> 服务器"))
        remote_to_client = threading.Thread(target=transfer_data,
                                            args=(remote_socket, client_socket, "服务器 -> 客户端"))

        client_to_remote.start()
        remote_to_client.start()

        client_to_remote.join()
        remote_to_client.join()
    except Exception as e:
        # print(f"处理客户端连接时发生错误: {e}")
        CTkMessagebox(title="错误", message=f"处理客户端连接时发生错误: {e}", icon="cancel")
    finally:
        client_socket.close()


def cleanup():
    try:
        modify_hosts(action="remove")
        print("已清理 hosts 文件")
    except Exception as e:
        print(f"清理 hosts 文件时发生错误: {e}")

    # 刷新 DNS 缓存
    flush_dns()
    print("已刷新 DNS 缓存")


def main():
    if not is_admin():
        print("u r not admin, program is restarting as admin...")
        try:
            run_as_admin()
        except Exception as err:
            print(f"ERROR: 无法以管理员权限运行。详细原因：{err}")

    atexit.register(cleanup)

    proxy_host = "0.0.0.0"
    proxy_port = 25565
    remote_host = "mc.hypixel.net"
    remote_port = 25565

    if is_domain(remote_host):
        try:
            modify_hosts(action="add", domain=remote_host, ip="127.0.0.1")
            print(f"已将 {remote_host} 添加到 hosts 文件中")
            print(f"直接在 Minecraft 中使用 {remote_host} 进行连接")
            flush_dns()
        except:
            print(f"无法将 {remote_host} 添加到 hosts 文件中")
        remote_host = socket.getaddrinfo(remote_host, None, family=socket.AF_INET)[0][4][0]
    else:
        print(f"在 Minecraft 中使用 127.0.0.1:{proxy_port} 进行连接")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((proxy_host, proxy_port))
    server.listen(5)

    print(f"代理服务器正在监听 {proxy_host}:{proxy_port}")

    try:
        while True:
            client_socket, addr = server.accept()
            print(f"接受来自 {addr[0]}:{addr[1]} 的连接")

            client_thread = threading.Thread(target=handle_client, args=(client_socket, remote_host, remote_port))
            client_thread.start()
    except KeyboardInterrupt:
        print("正在关闭代理服务器...")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        server.close()
        cleanup()
        input("看到这个说明已经成功清理了 hosts 文件和刷新了 DNS 缓存，按任意键退出...")


if __name__ == "__main__":
    main()
