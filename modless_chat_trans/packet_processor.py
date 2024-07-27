import json
import struct

CHAT_PACKET_ID = 0x39


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """
    解码变长整数（VarInt）

    :param data: 包含VarInt的字节串
    :param offset: 开始解码的位置偏移量
    :return: 一个元组，包含解码后的整数值和读取的字节数
    """

    value = 0
    shift = 0

    for i in range(5):  # VarInt最多5个字节
        byte = data[offset + i]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset + i + 1
        shift += 7

    raise ValueError("Varint is too long")


def encode_varint(value: int) -> bytes:
    """
    编码整数为变长整数（VarInt）

    :param value: 要编码的整数
    :return: 编码后的字节串
    """

    result = bytearray()
    while True:
        temp = value & 0x7F
        value >>= 7
        if value:
            result.append(temp | 0x80)
        else:
            result.append(temp)
            break
        return bytes(result)


def is_chat_packet(data):
    """
    判断数据包是否为Minecraft聊天消息数据包

    :param data: 原始数据包字节串
    :return: 如果是聊天消息数据包则返回True，否则返回False
    """

    try:
        _, pos = decode_varint(data)
        packet_id, _ = decode_varint(data, pos)
        return packet_id == CHAT_PACKET_ID
    except:
        return False


def parse_chat_message(data: bytes) -> str:
    """
    解析Minecraft聊天消息数据包

    :param data: 原始数据包字节串
    :return: 解析出的聊天消息文本，如果解析失败则返回None
    """

    try:
        # See: https://wiki.vg/Protocol#Player_Chat_Message
        # 下面的代码不确定
        # 跳过数据包ID和长度
        _, pos = decode_varint(data)
        _, pos = decode_varint(data, pos)

        # 解析JSON聊天消息
        json_length, pos = decode_varint(data, pos)
        json_data = data[pos:pos + json_length].decode("utf-8")
        chat_data = json.loads(json_data)

        # 提取纯文本消息
        if "text" in chat_data:
            return chat_data["text"]
        # 处理更复杂的消息结构
        elif "extra" in chat_data:
            return "".join(component.get("text", "") for component in chat_data["extra"])
    except Exception as e:
        print(f"解析聊天消息时出错: {e}")
    return ""


def modify_chat_message(data: bytes, new_message: str) -> bytes:
    """
    修改Minecraft聊天消息数据包中的消息内容

    :param data: 原始数据包字节串
    :param new_message: 新的聊天消息文本
    :return: 修改后的数据包字节串
    """

    try:
        # 跳过数据包ID和长度
        _, pos = decode_varint(data)
        _, pos = decode_varint(data, pos)

        # 解析JSON聊天消息
        json_length, pos = decode_varint(data, pos)
        json_data = data[pos:pos + json_length].decode('utf-8')
        chat_data = json.loads(json_data)

        # 修改消息内容
        if 'text' in chat_data:
            chat_data['text'] = new_message
        elif 'extra' in chat_data:
            for component in chat_data['extra']:
                if 'text' in component:
                    component['text'] = new_message

        # 序列化新的JSON消息
        new_json_data = json.dumps(chat_data).encode('utf-8')
        new_json_length = len(new_json_data)

        # 构建新的数据包
        new_data = bytearray()
        new_data.extend(encode_varint(CHAT_PACKET_ID))
        new_data.extend(encode_varint(new_json_length))
        new_data.extend(new_json_data)

        return bytes(new_data)

    except Exception as e:
        print(f"修改聊天消息时出错: {e}")
    return data