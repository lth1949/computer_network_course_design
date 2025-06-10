#!/usr/bin/env python3
"""
UDP服务器端程序
实现可靠传输协议，模拟TCP连接建立和数据传输
"""

import socket
import struct
import random
import time
import threading
import sys
import re
from typing import Dict, List, Tuple

# 协议常量
SYN = 0x01          # 同步标志
ACK = 0x02          # 确认标志
FIN = 0x04          # 结束标志
DATA = 0x08         # 数据标志
RST = 0x10          # 重置标志

# 协议状态
CLOSED = 0
LISTEN = 1
SYN_RECEIVED = 2
ESTABLISHED = 3
FIN_WAIT = 4

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
        self.connections: Dict[Tuple[str, int], Dict] = {}
        self.seq_num = 0
        
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
        packet = struct.pack('!BIIH', flags, seq_num, ack_num, length) + data
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
    
    def handle_connection_establishment(self, client_addr: Tuple[str, int], packet: bytes):
        """处理连接建立过程"""
        flags, seq_num, ack_num, length, data = self.parse_packet(packet)
        
        if flags is None:
            return
            
        if flags & SYN:
            print(f"收到来自 {client_addr} 的SYN包，序列号: {seq_num}")
            
            # 初始化连接状态
            self.connections[client_addr] = {
                'state': SYN_RECEIVED,
                'seq_num': random.randint(1000, 9999),
                'ack_num': seq_num + 1,
                'start_time': time.time()
            }
            
            # 发送SYN+ACK
            syn_ack_packet = self.create_packet(
                SYN | ACK,
                self.connections[client_addr]['seq_num'],
                self.connections[client_addr]['ack_num']
            )
            
            self.socket.sendto(syn_ack_packet, client_addr)
            print(f"发送SYN+ACK到 {client_addr}")
            
        elif flags & ACK and client_addr in self.connections:
            if self.connections[client_addr]['state'] == SYN_RECEIVED:
                self.connections[client_addr]['state'] = ESTABLISHED
                print(f"连接建立完成: {client_addr}")
    
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
            
        print(f"收到来自 {client_addr} 的数据包，序列号: {seq_num}, 长度: {length}")
        
        # 模拟丢包
        if self.should_drop_packet():
            print(f"模拟丢包: 序列号 {seq_num}")
            return
        
        # 发送确认
        ack_packet = self.create_packet(
            ACK,
            self.connections[client_addr]['seq_num'],
            seq_num + length
        )
        
        self.socket.sendto(ack_packet, client_addr)
        print(f"发送ACK到 {client_addr}, 确认序列号: {seq_num + length}")
        
        # 更新连接状态
        self.connections[client_addr]['ack_num'] = seq_num + length
    
    def handle_connection_termination(self, client_addr: Tuple[str, int], packet: bytes):
        """处理连接终止"""
        flags, seq_num, ack_num, length, data = self.parse_packet(packet)
        
        if flags is None:
            return
            
        if client_addr not in self.connections:
            print(f"收到来自未建立连接的客户端 {client_addr} 的FIN包")
            return
            
        if flags & FIN:
            print(f"收到来自 {client_addr} 的FIN包")
            
            # 发送FIN+ACK
            fin_ack_packet = self.create_packet(
                FIN | ACK,
                self.connections[client_addr]['seq_num'],
                seq_num + 1
            )
            
            self.socket.sendto(fin_ack_packet, client_addr)
            
            # 清理连接
            if client_addr in self.connections:
                del self.connections[client_addr]
            print(f"连接终止: {client_addr}")
    
    def run(self):
        """运行服务器"""
        print("服务器开始监听...")
        
        try:
            while True:
                try:
                    packet, client_addr = self.socket.recvfrom(1024)
                    
                    # 解析数据包
                    flags, seq_num, ack_num, length, data = self.parse_packet(packet)
                    
                    if flags is None:
                        print(f"收到无效数据包来自 {client_addr}")
                        continue
                    
                    # 根据标志位处理不同类型的包
                    if flags & SYN:
                        self.handle_connection_establishment(client_addr, packet)
                    elif flags & DATA:
                        self.handle_data_transmission(client_addr, packet)
                    elif flags & FIN:
                        self.handle_connection_termination(client_addr, packet)
                    elif flags & ACK:
                        # 处理纯ACK包
                        if client_addr in self.connections:
                            if self.connections[client_addr]['state'] == SYN_RECEIVED:
                                self.connections[client_addr]['state'] = ESTABLISHED
                                print(f"连接建立完成: {client_addr}")
                            self.connections[client_addr]['ack_num'] = ack_num
                    
                except socket.error as e:
                    print(f"Socket错误: {e}")
                    continue
                    
        except KeyboardInterrupt:
            print("\n服务器关闭")
        finally:
            self.socket.close()

def main():
    """主函数"""
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