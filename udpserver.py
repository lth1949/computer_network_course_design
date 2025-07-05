import socket
import struct
import random
import time
import threading
import sys
import re
from typing import Dict, List, Tuple

# 协议常量
SYN = 0x01          # 同步标志  00000001
ACK = 0x02          # 确认标志  00000010
FIN = 0x04          # 结束标志  00000100
DATA = 0x08         # 数据标志  00001000
RST = 0x10          # 重置标志  00010000

# 协议状态
CLOSED = 0          # 连接关闭
LISTEN = 1          # 监听状态
SYN_RECEIVED = 2    # 收到SYN包
ESTABLISHED = 3     # 连接已建立
FIN_WAIT = 4        # 等待结束

class UDPServer:
    def __init__(self, host='0.0.0.0', port=8888, drop_rate=0.1):
        """
        初始化UDP服务器
        
        Args:
            host: 服务器地址
            port: 服务器端口
            drop_rate: 丢包率 (0.0-1.0)
        """
        self.host = host
        self.port = port
        self.drop_rate = drop_rate
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        
        # 连接状态管理
        self.connections: Dict[Tuple[str, int], Dict] = {}  #Key：客户端地址元组 (IP, port)  Value：连接状态字典
        self.last_cleanup = time.time()       #上次清理超时连接的时间戳
        
        print(f"UDP服务器启动在 {host}:{port}")
        print(f"丢包率设置为: {drop_rate * 100}%")
        
    def create_packet(self, flags: int, seq_num: int, ack_num: int, data: bytes = b'') -> bytes:
        """
        创建协议数据包
        
        协议格式:
        +--------+--------+--------+--------+--------+
        | Flags  | SeqNum | AckNum | Length |  Data  |
        | 1 byte | 4 bytes| 4 bytes| 2 bytes| 0-80   |
        +--------+--------+--------+--------+--------+
        """
        length = len(data)
        packet = struct.pack('!BIIH', flags, seq_num, ack_num, length) + data #！：网络字节序大端模式，B：1字节，I：4字节，H：2字节
        return packet
    
    def parse_packet(self, packet: bytes) -> Tuple[int, int, int, int, bytes]:
        """
        解析协议数据包
        """
        if len(packet) < 11:  # 最小包长度
            return None, None, None, None, None
            
        header = packet[:11]
        data = packet[11:]
        
        try:
            flags, seq_num, ack_num, length = struct.unpack('!BIIH', header)
            return flags, seq_num, ack_num, length, data
        except struct.error:
            return None, None, None, None, None
    
    def should_drop_packet(self) -> bool:
        """决定是否丢弃数据包"""
        return random.random() < self.drop_rate
    
    def cleanup_expired_connections(self):
        """清理超时连接"""
        current_time = time.time()
        expired = []
        for addr, conn in self.connections.items():
            if current_time - conn['last_activity'] > 300:  # 5分钟超时
                expired.append(addr)
        
        #删除超时连接并打印日志
        for addr in expired:
            del self.connections[addr]
            print(f"清理超时连接: {addr}")
    
    def handle_connection_establishment(self, client_addr: Tuple[str, int], packet: bytes):
        """处理连接建立过程"""
        flags, seq_num, ack_num, length, data = self.parse_packet(packet)
        
        #如果数据包格式错误
        if flags is None:
            return
            
        if flags & SYN:
            print(f"收到来自 {client_addr} 的SYN包，序列号: {seq_num}")
            
            # 初始化连接状态
            self.connections[client_addr] = {
                'state': SYN_RECEIVED,
                'seq_num': random.randint(1000, 9999),  # 服务器初始序列号  在TCP三次握手中，客户端和服务器各自生成独立的随机初始序列号
                'ack_num': seq_num + 1,  # 期望的下一个序列号 (SYN占用一个序号)
                'start_time': time.time(),     #记录连接开始时间
                'last_activity': time.time()   #记录最后活动时间
            }
            
            # 发送SYN+ACK
            syn_ack_packet = self.create_packet(
                SYN | ACK, #按位或操作，表示将SYN和ACK标志位都设置为1
                self.connections[client_addr]['seq_num'],
                self.connections[client_addr]['ack_num']
            )
            
            self.socket.sendto(syn_ack_packet, client_addr)
            print(f"发送SYN+ACK到 {client_addr}, 序列号: {self.connections[client_addr]['seq_num']}, 确认号: {self.connections[client_addr]['ack_num']}")
            
        elif flags & ACK and client_addr in self.connections:
            if self.connections[client_addr]['state'] == SYN_RECEIVED:
                # 验证ACK号是否正确
                expected_ack = self.connections[client_addr]['seq_num'] + 1
                if ack_num == expected_ack:
                    self.connections[client_addr]['state'] = ESTABLISHED
                    self.connections[client_addr]['last_activity'] = time.time()
                    print(f"连接建立完成: {client_addr}")
                else:
                    print(f"无效的ACK号: {ack_num}, 期望 {expected_ack}")
    
    def handle_data_transmission(self, client_addr: Tuple[str, int], packet: bytes):
        """处理数据传输"""
        flags, seq_num, ack_num, length, data = self.parse_packet(packet)
        
        if flags is None:
            print(f"收到无效数据包来自 {client_addr}")
            return
            
        if client_addr not in self.connections:
            print(f"收到来自未建立连接的客户端 {client_addr} 的数据包")
            return
            
        if self.connections[client_addr]['state'] != ESTABLISHED:
            print(f"客户端 {client_addr} 连接状态不正确: {self.connections[client_addr]['state']}")
            return
            
        # 更新最后活动时间
        self.connections[client_addr]['last_activity'] = time.time()
        
        print(f"收到来自 {client_addr} 的数据包，序列号: {seq_num}, 长度: {length}, 期望序列号: {self.connections[client_addr]['ack_num']}")
        
        # 检查序列号是否匹配期望值
        if seq_num != self.connections[client_addr]['ack_num']:
            print(f"序列号不匹配: 收到 {seq_num}, 期望 {self.connections[client_addr]['ack_num']}")
            # 发送重复ACK
            ack_packet = self.create_packet(
                ACK,
                self.connections[client_addr]['seq_num'],
                self.connections[client_addr]['ack_num']
            )
            self.socket.sendto(ack_packet, client_addr)
            return
        
        # 模拟丢包
        if self.should_drop_packet():
            print(f"模拟丢包: 序列号 {seq_num}")
            return
        
        # 更新期望的序列号
        self.connections[client_addr]['ack_num'] = seq_num + length
        
        # 发送确认
        ack_packet = self.create_packet(
            ACK,
            self.connections[client_addr]['seq_num'],
            self.connections[client_addr]['ack_num']
        )
        
        self.socket.sendto(ack_packet, client_addr)
        print(f"发送ACK到 {client_addr}, 序列号: {self.connections[client_addr]['seq_num']}, 确认号: {self.connections[client_addr]['ack_num']}")
    
    def handle_connection_termination(self, client_addr: Tuple[str, int], packet: bytes):
        """处理连接终止"""
        flags, seq_num, ack_num, length, data = self.parse_packet(packet)
        
        if flags is None:
            return
            
        if client_addr not in self.connections:
            print(f"收到来自未建立连接的客户端 {client_addr} 的FIN包")
            return
            
        if flags & FIN:
            print(f"收到来自 {client_addr} 的FIN包，序列号: {seq_num}")
            
            # 发送FIN+ACK
            fin_ack_packet = self.create_packet(
                FIN | ACK,
                self.connections[client_addr]['seq_num'],
                seq_num + 1  # 确认号 = 收到的序列号 + 1
            )
            
            self.socket.sendto(fin_ack_packet, client_addr)
            
            # 清理连接
            if client_addr in self.connections:
                del self.connections[client_addr]
            print(f"连接终止: {client_addr}")
    
    def run(self):
        print("服务器开始监听...")
        last_cleanup = time.time()
        
        try:
            while True:
                try:
                    packet, client_addr = self.socket.recvfrom(1024)
                    
                    # 定期清理超时连接
                    if time.time() - last_cleanup > 60:  # 每分钟清理一次
                        self.cleanup_expired_connections()
                        last_cleanup = time.time()
                    
                    # 解析数据包
                    flags, seq_num, ack_num, length, data = self.parse_packet(packet)
                    
                    if flags is None:
                        print(f"收到无效数据包来自 {client_addr}")
                        continue
                    
                    # 根据标志位处理不同类型的包
                    if flags & (SYN | ACK):
                        self.handle_connection_establishment(client_addr, packet)
                    elif flags & DATA:
                        self.handle_data_transmission(client_addr, packet)
                    elif flags & FIN:
                        self.handle_connection_termination(client_addr, packet)
                    
                    
                except socket.error as e:
                    print(f"Socket错误: {e}")
                    continue
                    
        except KeyboardInterrupt:  #当用户想要停止服务器时，可以按下Ctrl+C，
                                   #程序会捕获到KeyboardInterrupt异常，打印一条消息，然后退出run方法
            print("\n服务器关闭")
        finally:
            self.socket.close()

def main():
    # 检查参数数量
    if len(sys.argv) != 4:
        print("错误: 参数数量不正确")
        print("使用方法: python udpserver.py <host> <port> <drop_rate>")
        print("示例: python udpserver.py 0.0.0.0 8888 0.1")
        sys.exit(1)
    
    # 获取参数
    host = sys.argv[1]
    port_str = sys.argv[2]
    drop_rate_str = sys.argv[3]
    
    # 验证端口号
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            print("错误: 端口号必须在1024-65535之间")
            sys.exit(1)
    except ValueError:
        print("错误: 端口号必须是整数")
        sys.exit(1)
    
    # 验证丢包率
    try:
        drop_rate = float(drop_rate_str)
        if drop_rate < 0.0 or drop_rate > 1.0:
            print("错误: 丢包率必须在0.0-1.0之间")
            sys.exit(1)
    except ValueError:
        print("错误: 丢包率必须是浮点数")
        sys.exit(1)
    
    # 验证主机地址 - 使用正则表达式
    # 允许的特殊地址
    special_addresses = ['0.0.0.0', 'localhost', '127.0.0.1']
    
    if host in special_addresses:
        # 特殊地址直接通过
        pass
    else:
        # 使用正则表达式验证IP地址格式
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(ip_pattern, host):
            print("错误: 主机地址格式不正确")
            print("支持的格式:")
            print("  - 特殊地址: 0.0.0.0, localhost, 127.0.0.1")
            print("  - IPv4地址: 例如 192.168.1.1")
            sys.exit(1)
    
    print(f"启动UDP服务器...")
    print(f"主机地址: {host}")
    print(f"端口: {port}")
    print(f"丢包率: {drop_rate}")
    
    server = UDPServer(host, port, drop_rate)
    server.run()

if __name__ == "__main__":
    main()