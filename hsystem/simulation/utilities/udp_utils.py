import socket
import struct

class UdpSendClient:
    def __init__(self, host, port):
        self._host = host   # 组播地址
        self._port = port   # 端口

        self._socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # 创建套接字
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)  # 设置组播TTL

    def send_data(self, data):
        raise NotImplementedError()

class UdpReceiveClient:
    def __init__(self, host, port):
        self._host = host   # 组播地址
        self._port = port   # 端口
        self._socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # 创建套接字
        self._socket.bind(("",port))
        self._socket.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton(self._host)+socket.inet_aton("0.0.0.0"))

    def get_data(self):
        raise NotImplementedError()

class UdpSendClient4radar14(UdpReceiveClient):
    def __init__(self, host, port):
        super().__init__(host, port)
        self._send_host = host
        self._send_host = port


        # 平台实体信息
        self.pack_info = ">HHHHIIH16sbbbbIiiiHHhhbIbbbH16sbbH16sHH"
        # 搜索命令
        self.pack_seek = ">HHHHIIHbHHHhhbbb"
        # 跟踪命令
        self.pack_follow = ">HHHHIIHbH3b"

    def get_data(self):
        """获取信息标识"""
        data,addr = self._socket.recvfrom(16500)    # 当没有收到消息时，该位置会处于阻塞状态
        sec = 2
        data_header = [data[i:i+sec]for i in range(0,len(data),sec)]
        if data_header[0] == b'\x10\x00':
            """
            搜索控制解码
            """
            seek_data = struct.unpack(self.pack_seek, data)
            print("获取14所雷达搜索结果")
            return seek_data
        else:
            return None

class UdpReceiveClient4radar14(UdpReceiveClient):
    def __init__(self, host, port):
        super().__init__(host, port)

    def send_data(self, data):
        """组播方式发送数据"""
        self._socket.sendto(data, ( self._host, self._port))
