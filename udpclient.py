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
CLOSED = 0          #连接处于关闭状态。这是TCP连接的初始状态和最终状态
SYN_SENT = 1        #客户端已经发送了SYN（同步）包以初始化连接，但尚未收到服务器的SYN-ACK（同步确认）响应
ESTABLISHED = 2     #连接已经成功建立，客户端和服务器可以进行数据传输
FIN_WAIT = 3        #客户端已经发送了FIN（终止）包以关闭连接，但尚未收到服务器的ACK（确认）响应

class UDPClient:
    def __init__(self, server_host: str, server_port: int):
        """
        初始化UDP客户端
        
        Args:
            server_host: 服务器地址
            server_port: 服务器端口
        """
        self.server_addr = (server_host, server_port)
        self.initial_timeout = 0.3  # 初始超时时间300ms
        self.timeout_interval = self.initial_timeout  # 当前超时时间
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.timeout_interval)
        
        # 连接状态
        self.state = CLOSED
        self.initial_seq_num = random.randint(1000, 9999)  # 初始序列号
        self.seq_num = self.initial_seq_num  # 当前序列号（基于字节位置）
        self.ack_num = 0
        
        # 滑动窗口参数
        self.window_size = 400  # 字节，固定发送窗口大小400字节
        self.base = self.initial_seq_num  # 窗口起始位置（初始化为初始序列号）
        self.next_seq_num = self.initial_seq_num  # 下一个要发送的字节位置
        
        # 字节计数
        self.total_bytes_sent = 0  # 累计发送的字节数
        
        # 数据包管理
        self.packets: Dict[int, Dict] = {}          # 已发送数据包 {序列号: 包信息}
        self.packet_times: Dict[int, float] = {}    # 包发送时间 {序列号: 时间戳}
        self.retransmit_count: Dict[int, int] = {}  # 重传次数 {序列号: 次数}
        
        # 统计信息
        self.rtt_list = []  # 存储所有RTT样本
        self.avg_rtt = 0.0  # 平均RTT
        self.total_packets = 0
        self.retransmitted_packets = 0
        self.expected_packets = 30
        
        # 线程锁
        self.lock = threading.Lock()        
        
        print(f"UDP客户端初始化完成")
        print(f"服务器地址: {server_host}:{server_port}")
        print(f"初始超时时间: {self.initial_timeout*1000:.0f}ms")
        print(f"窗口大小: {self.window_size}字节")
        print(f"初始序列号: {self.initial_seq_num}")
        
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
        syn_packet = self.create_packet(SYN, self.initial_seq_num, 0)
        self.socket.sendto(syn_packet, self.server_addr)
        print(f"发送SYN包，序列号: {self.initial_seq_num}")
        
        # 等待SYN+ACK
        try:
            packet, addr = self.socket.recvfrom(1024)
            flags, seq_num, ack_num, length, data = self.parse_packet(packet)
            
            if flags is None:
                print("收到无效响应")
                return False
                
            if flags & SYN and flags & ACK:
                print(f"收到SYN+ACK，服务器序列号: {seq_num}, 确认号: {ack_num}")
                
                # 验证确认号是否正确（应该是初始序列号+1）
                if ack_num != self.initial_seq_num + 1:
                    print(f"警告: 收到无效确认号 {ack_num}，期望 {self.initial_seq_num + 1}")
                
                # 发送ACK
                ack_packet = self.create_packet(ACK, self.initial_seq_num + 1, seq_num + 1)
                self.socket.sendto(ack_packet, self.server_addr)
                print("发送ACK确认连接建立")
                
                self.state = ESTABLISHED
                self.ack_num = seq_num + 1
                self.next_seq_num = self.initial_seq_num + 1  # 下一个数据包从初始序列号+1开始
                self.base = self.initial_seq_num + 1  # 窗口起始位置更新
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
            fin_packet = self.create_packet(FIN, self.next_seq_num, self.ack_num)
            self.socket.sendto(fin_packet, self.server_addr)
            
            # 等待FIN+ACK
            try:
                packet, addr = self.socket.recvfrom(1024)
                flags, seq_num, ack_num, length, data = self.parse_packet(packet)
                
                if flags & FIN and flags & ACK:
                    print("连接断开成功")
                    
                    # 发送最终ACK
                    ack_packet = self.create_packet(ACK, self.next_seq_num + 1, seq_num + 1)
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
            # 检查窗口是否已满（基于字节位置）
            if (self.next_seq_num - self.base) >= self.window_size:
                print(f"窗口已满 ({self.next_seq_num - self.base}/{self.window_size} 字节)，等待确认...")
                return False
            
            # 创建数据包
            packet = self.create_packet(DATA, self.next_seq_num, self.ack_num, data)
            data_length = len(data)
            
            # 发送数据包
            self.socket.sendto(packet, self.server_addr)
            
            # 记录发送信息
            start_byte = self.next_seq_num
            end_byte = start_byte + data_length - 1
            
            self.packets[self.next_seq_num] = {
                'id': packet_id,
                'data': data,
                'start_byte': start_byte,
                'end_byte': end_byte,
                'length': data_length
            }
            self.packet_times[self.next_seq_num] = time.time()
            self.retransmit_count[self.next_seq_num] = 0
            
            print(f"第{packet_id}个（第{start_byte}~{end_byte}字节，序列号:{self.next_seq_num}）client端已经发送")
            
            # 更新下一个序列号（基于字节位置）
            self.next_seq_num += data_length
            self.total_bytes_sent += data_length
            self.total_packets += 1
            
            return True
    
    def update_timeout_interval(self, rtt: float):
        """根据新的RTT样本更新超时时间"""
        # 将RTT添加到列表中
        self.rtt_list.append(rtt)
        
        # 计算新的平均RTT
        self.avg_rtt = sum(self.rtt_list) / len(self.rtt_list)
        
        # 设置新的超时时间为平均RTT的5倍（转换为秒）
        new_timeout = (self.avg_rtt * 5) / 1000.0
        
        # 确保超时时间不低于最小值
        min_timeout = 0.1  # 100ms
        if new_timeout < min_timeout:
            new_timeout = min_timeout
            
        # 更新超时时间
        self.timeout_interval = new_timeout
        
        # 更新socket超时设置
        self.socket.settimeout(self.timeout_interval)
    
    def handle_ack(self, ack_num: int):
        """处理确认包"""
        with self.lock:
            print(f"收到ACK确认号: {ack_num}, 当前base: {self.base}")
            
            # 检查确认号是否有效
            if ack_num < self.base:
                print(f"收到过时ACK: {ack_num} (当前base: {self.base})")
                return
            
            # 更新窗口起始位置
            self.base = ack_num
            print(f"更新窗口base为: {self.base}")
            
            # 清理已确认的数据包
            keys_to_remove = []
            for seq_num, packet_info in self.packets.items():
                # 如果数据包的结束位置 <= 确认号，说明已完全确认
                if packet_info['end_byte'] < ack_num:
                    # 计算RTT
                    if seq_num in self.packet_times:
                        rtt = (time.time() - self.packet_times[seq_num]) * 1000  # 转换为毫秒
                        if rtt < 0.01:
                            rtt = 0.01
                        
                        # 使用新的RTT样本更新超时时间
                        self.update_timeout_interval(rtt)
                        
                        print(f"第{packet_info['id']}个（第{packet_info['start_byte']}~{packet_info['end_byte']}字节，序列号:{seq_num}）server端已经收到，RTT是{rtt:.2f}ms")
                    
                    keys_to_remove.append(seq_num)
            
            # 删除已确认的数据包
            for seq_num in keys_to_remove:
                del self.packets[seq_num]
                if seq_num in self.packet_times:
                    del self.packet_times[seq_num]
                if seq_num in self.retransmit_count:
                    del self.retransmit_count[seq_num]
    
    def retransmit_packets(self):
        """重传超时的数据包"""
        current_time = time.time()
        retransmit_list = []
        failed_packets = []
        
        with self.lock:
            # 找出所有超时的数据包
            for seq_num, send_time in self.packet_times.items():
                if current_time - send_time > self.timeout_interval:
                    retransmit_list.append(seq_num)
        
        for seq_num in retransmit_list:
            if seq_num in self.packets:
                packet_info = self.packets[seq_num]
                data = packet_info['data']
                
                # 检查重传次数
                retry_count = self.retransmit_count.get(seq_num, 0)
                if retry_count >= 5:  # 最大重传次数限制
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
                
                print(f"重传第{packet_info['id']}个（第{packet_info['start_byte']}~{packet_info['end_byte']}字节，序列号:{seq_num}）数据包 (第{retry_count + 1}次重传)")
        
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
        while self.state == ESTABLISHED:      #循环监听
            try:
                packet, addr = self.socket.recvfrom(1024)
                flags, seq_num, ack_num, length, data = self.parse_packet(packet)
                
                if flags is None:
                    continue
                
                if flags & ACK:
                    self.handle_ack(ack_num)
                    
            except socket.timeout:  #如果捕获到 socket.timeout 异常，表示接收数据时超时，继续等待下一个数据包
                continue
            except Exception as e:
                print(f"接收确认包错误: {e}")
                break
    
    def send_data(self):
        """发送数据"""
        print("开始发送数据...")
        
        # 启动接收确认包的线程（发数据和接受ack两个线程）
        ack_thread = threading.Thread(target=self.receive_acks)
        ack_thread.daemon = True  #设置为守护线程，当主线程结束时，这个线程也会被强制结束
        ack_thread.start()        #启动线程
        
        packet_id = 1
        bytes_sent = 0
        max_packets = self.expected_packets   #发30个数据包包
        
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
                remaining_bytes = self.next_seq_num - self.base
                print(f"等待确认中... 剩余未确认字节: {remaining_bytes} (窗口使用: {remaining_bytes}/{self.window_size})")
                print(f"当前超时时间: {self.timeout_interval*1000:.2f}ms, 平均RTT: {self.avg_rtt:.2f}ms")
        
        if self.base < self.next_seq_num:
            remaining_bytes = self.next_seq_num - self.base
            print(f"警告: {remaining_bytes} 字节数据未收到确认")
            
            # 打印未确认的数据包信息
            with self.lock:
                for seq_num in sorted(self.packets.keys()):
                    if seq_num >= self.base:
                        packet_info = self.packets[seq_num]
                        retry_count = self.retransmit_count.get(seq_num, 0)
                        print(f"  数据包 {packet_info['id']} (序列号: {seq_num}, 字节: {packet_info['start_byte']}-{packet_info['end_byte']}) 重传 {retry_count} 次后仍未确认")
        
        print("数据传输完成")
    
    def print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("传输统计信息")
        print("=" * 60)
        
        # 计算失败的数据包数
        failed_packets = 0
        with self.lock:
            for seq_num, packet_info in self.packets.items():
                if seq_num >= self.base:  # 只统计未确认的数据包
                    failed_packets += 1
        
        # 计算成功传输的包数
        success_packets = len(self.rtt_list)
        
        # 计算总发送包数（包括重传）
        total_transmissions = self.total_packets + self.retransmitted_packets
        
        # 计算丢包率（重传包数 / 总传输次数）
        drop_rate = 0.0
        if total_transmissions > 0:
            drop_rate = (self.retransmitted_packets / total_transmissions) * 100
        
        # 使用pandas计算RTT统计
        rtt_min = rtt_max = rtt_avg = rtt_std = 0.0
        if self.rtt_list:
            rtt_series = pd.Series(self.rtt_list)
            rtt_min = rtt_series.min()
            rtt_max = rtt_series.max()
            rtt_avg = rtt_series.mean()
            rtt_std = rtt_series.std()
        
        # 打印简化统计信息
        print(f"RTT最小值: {rtt_min:.2f}ms")
        print(f"RTT最大值: {rtt_max:.2f}ms")
        print(f"RTT平均值: {rtt_avg:.2f}ms")
        print(f"RTT标准差: {rtt_std:.2f}ms")
        print(f"总发送包数: {self.total_packets}")
        print(f"重传包数: {self.retransmitted_packets}")
        print(f"成功传输包数: {success_packets}")
        print(f"失败包数: {failed_packets}")
        print(f"总传输字节数: {self.total_bytes_sent}")
        print(f"网络丢包率: {drop_rate:.2f}%")
        print(f"最终超时时间: {self.timeout_interval*1000:.2f}ms")
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
    
    # 检查参数数量
    if len(sys.argv) != 3:
        print("错误: 参数数量不正确")
        print("使用方法: python udpclient.py <server_host> <server_port>")
        print("示例: python udpclient.py 127.0.0.1 8888")
        sys.exit(1)
    
    # 获取参数
    server_host = sys.argv[1]
    port_str = sys.argv[2]
    
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
    print(f"初始超时时间: 300ms")
    
    client = UDPClient(server_host, server_port)
    client.run()

if __name__ == "__main__":
    main()