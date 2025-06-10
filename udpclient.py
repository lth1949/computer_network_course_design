#!/usr/bin/env python3
"""
UDP客户端程序
实现可靠传输协议，模拟TCP连接建立和数据传输
包括滑动窗口、超时重传、RTT统计等功能
"""

import socket
import struct
import random
import time
import threading
import sys
import re
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import deque

# 协议常量
SYN = 0x01          # 同步标志
ACK = 0x02          # 确认标志
FIN = 0x04          # 结束标志
DATA = 0x08         # 数据标志
RST = 0x10          # 重置标志

# 协议状态
CLOSED = 0
SYN_SENT = 1
ESTABLISHED = 2
FIN_WAIT = 3

class UDPClient:
    def __init__(self, server_host: str, server_port: int, timeout=300):
        """
        初始化UDP客户端
        
        Args:
            server_host: 服务器地址
            server_port: 服务器端口
            timeout: 超时时间(毫秒)
        """
        self.server_addr = (server_host, server_port)
        self.timeout = timeout / 1000.0  # 转换为秒
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.timeout)
        
        # 连接状态
        self.state = CLOSED
        self.seq_num = random.randint(1000, 9999)
        self.ack_num = 0
        
        # 滑动窗口参数 - 符合实验要求
        self.window_size = 400  # 字节，固定发送窗口大小400字节
        self.base = 0
        self.next_seq_num = 0
        
        # 字节计数
        self.total_bytes_sent = 0  # 累计发送的字节数
        
        # 数据包管理
        self.packets = {}  # 存储已发送的数据包
        self.packet_times = {}  # 存储发送时间
        self.retransmit_count = {}  # 重传次数
        
        # 统计信息
        self.rtt_list = []
        self.total_packets = 0
        self.retransmitted_packets = 0
        self.expected_packets = 30
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 连接建立标志
        self.connection_established = False
        
        print(f"UDP客户端初始化完成")
        print(f"服务器地址: {server_host}:{server_port}")
        print(f"超时时间: {timeout}ms")
        print(f"窗口大小: {self.window_size}字节")
        
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
    
    def connect(self) -> bool:
        """建立连接"""
        print("开始建立连接...")
        
        # 发送SYN包
        syn_packet = self.create_packet(SYN, self.seq_num, 0)
        self.socket.sendto(syn_packet, self.server_addr)
        print(f"发送SYN包，序列号: {self.seq_num}")
        
        # 等待SYN+ACK
        try:
            packet, addr = self.socket.recvfrom(1024)
            flags, seq_num, ack_num, length, data = self.parse_packet(packet)
            
            if flags is None:
                print("收到无效响应")
                return False
                
            if flags & SYN and flags & ACK:
                print(f"收到SYN+ACK，服务器序列号: {seq_num}, 确认号: {ack_num}")
                
                # 发送ACK
                ack_packet = self.create_packet(ACK, self.seq_num + 1, seq_num + 1)
                self.socket.sendto(ack_packet, self.server_addr)
                print("发送ACK确认连接建立")
                
                self.state = ESTABLISHED
                self.ack_num = seq_num + 1
                self.connection_established = True
                self.next_seq_num = self.seq_num + 1
                self.base = self.seq_num + 1
                print("连接建立成功")
                return True
            else:
                print("连接建立失败")
                return False
                
        except socket.timeout:
            print("连接超时")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.state == ESTABLISHED:
            print("开始断开连接...")
            
            # 发送FIN包
            fin_packet = self.create_packet(FIN, self.seq_num, self.ack_num)
            self.socket.sendto(fin_packet, self.server_addr)
            
            # 等待FIN+ACK
            try:
                packet, addr = self.socket.recvfrom(1024)
                flags, seq_num, ack_num, length, data = self.parse_packet(packet)
                
                if flags & FIN and flags & ACK:
                    print("连接断开成功")
                    
                    # 发送ACK
                    ack_packet = self.create_packet(ACK, self.seq_num + 1, seq_num + 1)
                    self.socket.sendto(ack_packet, self.server_addr)
                    
            except socket.timeout:
                print("断开连接超时")
            
            self.state = CLOSED
    
    def generate_data(self, size: int) -> bytes:
        """生成测试数据"""
        return b'X' * size
    
    def send_packet(self, packet_id: int, data: bytes) -> bool:
        """发送数据包"""
        with self.lock:
            # 检查窗口是否已满
            if self.total_bytes_sent - self.base >= self.window_size:
                return False
            
            # 创建数据包
            packet = self.create_packet(DATA, self.next_seq_num, self.ack_num, data)
            
            # 发送数据包
            self.socket.sendto(packet, self.server_addr)
            
            # 记录发送信息
            start_byte = self.total_bytes_sent
            end_byte = start_byte + len(data) - 1
            
            self.packets[self.next_seq_num] = {
                'id': packet_id,
                'data': data,
                'start_byte': start_byte,
                'end_byte': end_byte,
                'seq_num': self.next_seq_num
            }
            self.packet_times[self.next_seq_num] = time.time()
            self.retransmit_count[self.next_seq_num] = 0
            
            print(f"第{packet_id}个（第{start_byte}~{end_byte}字节，序列号:{self.next_seq_num}）client端已经发送")
            
            self.next_seq_num += 1  # 序列号递增1
            self.total_bytes_sent += len(data)  # 字节数按实际数据长度递增
            self.total_packets += 1
            
            return True
    
    def handle_ack(self, ack_num: int):
        """处理确认包"""
        with self.lock:
            # 累积确认 - 基于序列号确认
            while self.base < ack_num:
                if self.base in self.packet_times:
                    # 计算RTT，使用更高精度的计时
                    rtt = (time.time() - self.packet_times[self.base]) * 1000  # 转换为毫秒
                    if rtt < 0.01:
                        rtt = 0.01
                    self.rtt_list.append(rtt)
                    
                    packet_info = self.packets[self.base]
                    print(f"第{packet_info['id']}个（第{packet_info['start_byte']}~{packet_info['end_byte']}字节，序列号:{packet_info['seq_num']}）server端已经收到，RTT是{rtt:.2f}ms")
                    
                    # 清理已确认的数据包
                    del self.packets[self.base]
                    del self.packet_times[self.base]
                    if self.base in self.retransmit_count:
                        del self.retransmit_count[self.base]
                
                self.base += 1
    
    def retransmit_packets(self):
        """重传超时的数据包"""
        current_time = time.time()
        retransmit_list = []
        failed_packets = []
        
        with self.lock:
            for seq_num, send_time in self.packet_times.items():
                if current_time - send_time > self.timeout:
                    retransmit_list.append(seq_num)
        
        for seq_num in retransmit_list:
            if seq_num in self.packets:
                packet_info = self.packets[seq_num]
                data = packet_info['data']
                
                # 检查重传次数，避免无限重传
                retry_count = self.retransmit_count.get(seq_num, 0)
                if retry_count >= 5:  # 增加重传次数限制到5次
                    print(f"数据包 {packet_info['id']} 重传次数过多({retry_count}次)，标记为失败")
                    failed_packets.append(seq_num)
                    continue
                
                # 重新发送
                packet = self.create_packet(DATA, seq_num, self.ack_num, data)
                self.socket.sendto(packet, self.server_addr)
                
                # 更新发送时间和重传计数
                self.packet_times[seq_num] = current_time
                self.retransmit_count[seq_num] = retry_count + 1
                self.retransmitted_packets += 1
                
                print(f"重传第{packet_info['id']}个（第{packet_info['start_byte']}~{packet_info['end_byte']}字节，序列号:{packet_info['seq_num']}）数据包 (第{retry_count + 1}次重传)")
        
        # 清理失败的数据包
        for seq_num in failed_packets:
            if seq_num in self.packets:
                packet_info = self.packets[seq_num]
                print(f"移除失败的数据包 {packet_info['id']} (序列号: {seq_num})")
                del self.packets[seq_num]
                if seq_num in self.packet_times:
                    del self.packet_times[seq_num]
                if seq_num in self.retransmit_count:
                    del self.retransmit_count[seq_num]
    
    def receive_acks(self):
        """接收确认包的线程函数"""
        while self.state == ESTABLISHED:
            try:
                packet, addr = self.socket.recvfrom(1024)
                flags, seq_num, ack_num, length, data = self.parse_packet(packet)
                
                if flags is None:
                    continue
                
                if flags & ACK:
                    self.handle_ack(ack_num)
                    
            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收确认包错误: {e}")
                break
    
    def send_data(self):
        """发送数据"""
        print("开始发送数据...")
        
        # 启动接收确认包的线程
        ack_thread = threading.Thread(target=self.receive_acks)
        ack_thread.daemon = True
        ack_thread.start()
        
        packet_id = 1
        bytes_sent = 0
        max_packets = self.expected_packets
        
        while packet_id <= max_packets:
            # 生成随机大小的数据包 (40-80字节)
            data_size = random.randint(40, 80)
            data = self.generate_data(data_size)
            
            # 尝试发送数据包
            if self.send_packet(packet_id, data):
                bytes_sent += data_size
                packet_id += 1
            else:
                # 窗口已满，等待一下
                time.sleep(0.01)
            
            # 检查是否需要重传
            self.retransmit_packets()
            
            # 短暂休眠
            time.sleep(0.01)
        
        # 等待所有数据包被确认，增加超时保护
        wait_count = 0
        max_wait_time = 30  # 最多等待30秒
        
        while self.base < self.next_seq_num and wait_count < max_wait_time * 10:  # 每0.1秒检查一次
            time.sleep(0.1)
            self.retransmit_packets()
            wait_count += 1
            
            # 每5秒打印一次等待状态
            if wait_count % 50 == 0:
                remaining_packets = self.next_seq_num - self.base
                print(f"等待确认中... 剩余 {remaining_packets} 个数据包未确认")
        
        if self.base < self.next_seq_num:
            remaining_packets = self.next_seq_num - self.base
            print(f"警告: {remaining_packets} 个数据包未收到确认")
            
            # 打印未确认的数据包信息
            with self.lock:
                for seq_num in range(self.base, self.next_seq_num):
                    if seq_num in self.packets:
                        packet_info = self.packets[seq_num]
                        retry_count = self.retransmit_count.get(seq_num, 0)
                        print(f"  数据包 {packet_info['id']} (序列号: {seq_num}) 重传 {retry_count} 次后仍未确认")
        
        print("数据传输完成")
    
    def print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("传输统计信息")
        print("=" * 60)
        
        # 计算失败的数据包
        failed_packets = 0
        with self.lock:
            for seq_num in range(self.base, self.next_seq_num):
                if seq_num in self.packets:
                    failed_packets += 1
        
        # 丢包率计算
        total_sent = self.total_packets + self.retransmitted_packets
        if total_sent > 0:
            drop_rate = (self.retransmitted_packets / total_sent) * 100
            print(f"网络丢包率: {drop_rate:.2f}%")
        
        # 传输成功率
        if self.total_packets > 0:
            success_rate = ((self.total_packets - failed_packets) / self.total_packets) * 100
            print(f"传输成功率: {success_rate:.2f}%")
        
        # RTT统计
        if self.rtt_list:
            rtt_series = pd.Series(self.rtt_list)
            print(f"最大RTT: {rtt_series.max():.2f}ms")
            print(f"最小RTT: {rtt_series.min():.2f}ms")
            print(f"平均RTT: {rtt_series.mean():.2f}ms")
            print(f"RTT标准差: {rtt_series.std():.2f}ms")
        
        print(f"总发送包数: {self.total_packets}")
        print(f"重传包数: {self.retransmitted_packets}")
        print(f"成功传输包数: {len(self.rtt_list)}")
        print(f"失败包数: {failed_packets}")
        
        # 重传统计
        if self.retransmit_count:
            max_retries = max(self.retransmit_count.values())
            avg_retries = sum(self.retransmit_count.values()) / len(self.retransmit_count)
            print(f"最大重传次数: {max_retries}")
            print(f"平均重传次数: {avg_retries:.2f}")
        
        print("=" * 60)
    
    def run(self):
        """运行客户端"""
        try:
            # 建立连接
            if not self.connect():
                print("连接失败")
                return
            
            # 发送数据
            self.send_data()
            
            # 断开连接
            self.disconnect()
            
            # 打印统计信息
            self.print_statistics()
            
        except Exception as e:
            print(f"运行错误: {e}")
        finally:
            self.socket.close()

def main():
    """主函数"""
    # 检查参数数量
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("错误: 参数数量不正确")
        print("使用方法: python udpclient.py <server_host> <server_port> [timeout]")
        print("示例: python udpclient.py 127.0.0.1 8888 300")
        sys.exit(1)
    
    # 获取参数
    server_host = sys.argv[1]
    port_str = sys.argv[2]
    timeout = 300  # 默认超时时间
    
    # 如果有超时参数
    if len(sys.argv) == 4:
        timeout_str = sys.argv[3]
        try:
            timeout = int(timeout_str)
            if timeout < 1 or timeout > 10000:
                print("错误: 超时时间必须在1-10000毫秒之间")
                sys.exit(1)
        except ValueError:
            print("错误: 超时时间必须是整数")
            sys.exit(1)
    
    # 验证端口号
    try:
        server_port = int(port_str)
        if server_port < 1024 or server_port > 65535:
            print("错误: 端口号必须在1024-65535之间")
            sys.exit(1)
    except ValueError:
        print("错误: 端口号必须是整数")
        sys.exit(1)
    
    # 验证服务器地址 - 使用正则表达式
    # 允许的特殊地址
    special_addresses = ['localhost', '127.0.0.1']
    
    if server_host in special_addresses:
        # 特殊地址直接通过
        pass
    else:
        # 使用正则表达式验证IP地址格式
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(ip_pattern, server_host):
            print("错误: 服务器地址格式不正确")
            print("支持的格式:")
            print("  - 特殊地址: localhost, 127.0.0.1")
            print("  - IPv4地址: 例如 192.168.1.1")
            sys.exit(1)
    
    print(f"启动UDP客户端...")
    print(f"服务器地址: {server_host}:{server_port}")
    print(f"超时时间: {timeout}ms")
    
    client = UDPClient(server_host, server_port, timeout)
    client.run()

if __name__ == "__main__":
    main() 