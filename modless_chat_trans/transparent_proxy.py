import socket
import threading
import re
import time
import sys
import ctypes


def is_domain(host):
    """
    判断是否为域名
    :param host: 要判断的主机名
    :return: 布尔值，表示是否为域名
    """

    domain_regex = re.compile(
        r'^(?:[a-zA-Z0-9]'
        r'(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)'
        r'+[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]$'
    )
    return bool(domain_regex.match(host))


def edit_hosts(domain, ip):
    """
    修改hosts

    :param domain: 域名
    :param ip: IP地址
    """

    # 获取管理员权限
    # 修改hosts文件:
    # 1.hosts_file = open('path_to_hosts', 'a')
    # 2.hosts_file.write(f'\n{ip} {domain} #Modless Chat Trans transparent proxy\n')
    # 3.hosts_file.close()
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    try:
        with open(r"C:\Windows\System32\drivers\etc\hosts", 'r') as hosts_file:
            hosts_content = hosts_file.read()
        # 如果不包含该条目，则添加
        if f"{ip} {domain}" not in hosts_content:
            with open(r"C:\Windows\System32\drivers\etc\hosts", 'a') as hosts_file:
                hosts_file.write(f'\n{ip} {domain} #Modless Chat Trans transparent proxy\n')
        return True
    except:
        return False
    # 重启网络服务
    # 返回是否修改成功


def transfer_and_monitor_data(client_socket, remote_host, remote_port):
    print(f"尝试连接到 {remote_host}:{remote_port}")
    try:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(30)  # 增加超时时间到30秒
        remote_socket.connect((remote_host, remote_port))
        print(f"成功连接到 {remote_host}:{remote_port}")

        def forward(src, dst, direction):
            total_data = 0
            try:
                while True:
                    data = src.recv(4096)
                    if not data:
                        break
                    dst.send(data)
                    total_data += len(data)
                    print(f"{direction} 转发: {len(data)} 字节")
            except Exception as e:
                print(f"{direction} 转发错误: {e}")
            finally:
                print(f"{direction} 总共转发: {total_data} 字节")
                src.close()

        client_thread = threading.Thread(target=forward, args=(client_socket, remote_socket, "客户端 -> 服务器"))
        remote_thread = threading.Thread(target=forward, args=(remote_socket, client_socket, "服务器 -> 客户端"))

        client_thread.start()
        remote_thread.start()

        client_thread.join()
        remote_thread.join()
    except Exception as e:
        print(f"处理客户端连接时发生错误: {e}")
    finally:
        client_socket.close()


def cleanup_proxy_settings():
    """
    清理代理设置，例如从 hosts 文件中删除添加的条目
    """

    # 清理代理设置
    # 例如，删除 hosts 文件中的特定条目
    with open(r"C:\Windows\System32\drivers\etc\hosts", 'r') as hosts_file:
        hosts_content = hosts_file.read()
        # 删除特定条目
        # 略
        # 将修改后的内容写回文件
    with open(r"C:\Windows\System32\drivers\etc\hosts", 'w') as hosts_file:
        hosts_file.write(hosts_content)


def main():
    proxy_host = '0.0.0.0'
    proxy_port = 25565

    remote_host = 'mc.hypixel.net'
    remote_port = 25565

    if is_domain(remote_host):
        if edit_hosts(remote_host, "127.0.0.1"):
            print(f"已将 {remote_host} 添加到 hosts 文件中")
            print(f"直接在Minecraft中使用 {remote_host} 进行连接")
        else:
            print(f"无法将 {remote_host} 添加到 hosts 文件中")
        remote_host = socket.getaddrinfo(remote_host, None, family=socket.AF_INET)
        # remote_host = socket.gethostbyname(remote_host)
        # remote_host = "172.65.206.176"
    else:
        print(f"在Minecraft中使用 127.0.0.1:25565 进行连接")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((proxy_host, proxy_port))
    server.listen(5)

    print(f"代理服务器正在监听 {proxy_host}:{proxy_port}")

    while True:
        try:
            client_socket, addr = server.accept()
            print(f"接受来自 {addr[0]}:{addr[1]} 的连接")

            proxy_thread = threading.Thread(target=transfer_and_monitor_data,
                                            args=(client_socket, remote_host, remote_port))
            proxy_thread.start()
        except Exception as e:
            print(f"接受连接时发生错误: {e}")


if __name__ == "__main__":
    main()
