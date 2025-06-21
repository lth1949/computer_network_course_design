# 2024 北林计算机网络课程设计 - TCP/UDP 程序

本项目包含四个网络通信程序：一个基于 TCP 的字符串反转服务（包含客户端和服务器），一个基于 UDP 的可靠传输协议实现（包含客户端和服务器）。

## 项目结构

```
computer_network_course_design/
├── README.md                 # 本说明文档
├── reversetcpclient.py      # TCP客户端程序
├── reversetcpserver.py      # TCP服务器程序
├── udpclient.py             # UDP客户端程序
└── udpserver.py             # UDP服务器程序
```

## 运行环境要求

### 系统要求

- **操作系统**: Windows 10/11, Linux, macOS
- **Python 版本**: Python 3.6 或更高版本
- **网络**: 支持 TCP/IP 协议的网络环境

### 依赖包

```bash
# 核心依赖（Python标准库，无需额外安装）
import socket
import struct
import random
import time
import threading
import sys
import re
import pandas as pd  # 用于RTT统计分析
```

### 安装 pandas（可选）

如果系统中没有安装 pandas，可以使用以下命令安装：

```bash
pip install pandas
```

---

# 第一部分：TCP 字符串反转服务

## TCP 程序概述

TCP 部分实现了一个基于 TCP 的字符串反转服务，包含客户端和服务器两个程序。客户端将文件内容分块发送给服务器，服务器对每个字符串块进行反转处理并返回结果。

## TCP 程序说明

### 1. TCP 客户端程序 (reversetcpclient.py)

#### 运行参数

```bash
python reversetcpclient.py <server_ip> <server_port> <Lmin> <Lmax> <input_file>
```

**参数说明**:

- `server_ip`: 服务器 IP 地址
  - 支持特殊地址: `localhost`, `127.0.0.1`
  - 支持 IPv4 地址: 例如 `192.168.1.1`
- `server_port`: 服务器端口号 (1024-65535)
- `Lmin`: 最小分块大小 (0-888 字符)
- `Lmax`: 最大分块大小 (1-888 字符，必须 ≥Lmin)
- `input_file`: 输入文件路径

**使用示例**:

```bash
# 基本用法
python reversetcpclient.py 127.0.0.1 8888 10 50 input.txt

# 使用localhost
python reversetcpclient.py localhost 8888 20 100 test.txt

# 小分块传输
python reversetcpclient.py 127.0.0.1 8888 5 20 small.txt
```

#### 输出文件

程序会自动生成反转后的输出文件，文件名为原文件名加上`_reversed.txt`后缀。
例如：`input.txt` → `input_reversed.txt`

### 2. TCP 服务器程序 (reversetcpserver.py)

#### 运行参数

```bash
python reversetcpserver.py <port>
```

**参数说明**:

- `port`: 服务器监听端口 (1024-65535)

**使用示例**:

```bash
# 基本用法
python reversetcpserver.py 8888

# 使用其他端口
python reversetcpserver.py 9999
```

## TCP 配置选项

### TCP 客户端配置

在`reversetcpclient.py`中可以修改以下配置：

```python
# 分块大小范围
Lmin = 10  # 最小分块
Lmax = 50  # 最大分块

# 最大分块限制
if Lmax > 888:  # 最大888字符
```

### TCP 服务器配置

在`reversetcpserver.py`中可以修改以下配置：

```python
# 服务器绑定地址
server_socket.bind(('172.31.53.98', port))

# 最大连接队列长度
server_socket.listen(5)
```

## TCP 程序使用流程

1. **启动 TCP 服务器**:

   ```bash
   python reversetcpserver.py 8888
   ```

2. **准备输入文件**:
   创建一个文本文件，例如`input.txt`

3. **启动 TCP 客户端**:

   ```bash
   python reversetcpclient.py 127.0.0.1 8888 10 50 input.txt
   ```

4. **查看结果**:
   - 控制台输出反转的字符串块
   - 生成`input_reversed.txt`文件

---

# 第二部分：UDP 可靠传输协议

## UDP 程序概述

UDP 部分实现了一个基于 UDP 的可靠传输协议，包含客户端和服务器两个程序。该协议通过滑动窗口、超时重传、序列号等机制来保证数据传输的可靠性。

## UDP 程序说明

### 1. UDP 客户端程序 (udpclient.py)

#### 运行参数

```bash
python udpclient.py <server_host> <server_port>
```

**参数说明**:

- `server_host`: 服务器 IP 地址
  - 支持特殊地址: `localhost`, `127.0.0.1`
  - 支持 IPv4 地址: 例如 `192.168.1.1`
- `server_port`: 服务器端口号 (1024-65535)

**使用示例**:

```bash
# 基本用法
python udpclient.py 127.0.0.1 8888

# 使用localhost
python udpclient.py localhost 8888
```

#### 输出信息

- 连接建立过程
- 数据包发送和接收状态
- 重传信息
- 传输统计信息（丢包率、RTT 统计等）

### 2. UDP 服务器程序 (udpserver.py)

#### 运行参数

```bash
python udpserver.py <host> <port> <drop_rate>
```

**参数说明**:

- `host`: 服务器监听地址
  - 支持特殊地址: `0.0.0.0`, `localhost`, `127.0.0.1`
  - 支持 IPv4 地址: 例如 `192.168.1.1`
- `port`: 服务器监听端口 (1024-65535)
- `drop_rate`: 丢包率 (0.0-1.0，例如 0.1 表示 10%丢包率)

**使用示例**:

```bash
# 基本用法
python udpserver.py 0.0.0.0 8888 0.1

# 无丢包模式
python udpserver.py 0.0.0.0 8888 0.0

# 高丢包率测试
python udpserver.py 0.0.0.0 8888 0.3

# 使用localhost
python udpserver.py localhost 8888 0.05
```

#### 输出信息

- 服务器启动信息
- 客户端连接建立过程
- 数据包接收和确认状态
- 模拟丢包信息
- 连接终止信息

## UDP 配置选项

### UDP 客户端配置

在`udpclient.py`中可以修改以下配置：

```python
# 初始超时时间（秒）
self.initial_timeout = 0.3  # 300ms

# 最小超时时间（秒）
min_timeout = 0.1  # 100ms

# 超时倍数因子
timeout_factor = 5  # 超时时间 = 平均RTT × 5

# 滑动窗口大小（字节）
self.window_size = 400

# 预期发送的数据包数量
self.expected_packets = 30

# 数据包大小范围（字节）
data_size = random.randint(40, 80)

# 重传次数限制
if retry_count >= 5:  # 最多重传5次
```

### UDP 服务器配置

在`udpserver.py`中可以修改以下配置：

```python
# 默认丢包率
drop_rate = 0.1  # 10%丢包率

# 服务器绑定地址
self.socket.bind((host, port))

# 连接状态管理
self.connections: Dict[Tuple[str, int], Dict] = {}
```

## UDP 程序使用流程

1. **启动 UDP 服务器**:

   ```bash
   python udpserver.py 0.0.0.0 8888 0.1
   ```

2. **启动 UDP 客户端**:

   ```bash
   python udpclient.py 127.0.0.1 8888
   ```

3. **观察输出**:
   - 服务器端：连接建立、数据包接收、确认发送
   - 客户端：连接建立、数据包发送、重传、统计信息

---

## 注意事项

1. **防火墙设置**: 确保防火墙允许程序使用指定端口
2. **权限问题**: 某些端口可能需要管理员权限
3. **网络环境**: 确保网络连接正常
4. **文件编码**: 输入文件建议使用 UTF-8 编码
5. **并发限制**: TCP 服务器默认支持 5 个并发连接
6. **UDP 丢包模拟**: UDP 服务器可以模拟网络丢包，用于测试客户端重传机制
7. **pandas 依赖**: 如未安装 pandas，UDP 客户端的 RTT 统计功能将受限
