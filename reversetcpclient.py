import sys     
import re
import random
import struct
import socket
import os
#import time

def main():
    #检查参数个数和读取参数
    if len(sys.argv) != 6:
        print("Error: Invalid number of arguments")
        print("Usage: python reversetcpclient.py <server_ip> <server_port> <Lmin> <Lmax> <input_file>")
        print("Example: python reversetcpclient.py 127.0.0.1 8888 10 50 input.txt")
        print("Parameters:")
        print("  server_ip: Server IP address")
        print("  server_port: Server port (1024-65535)")
        print("  Lmin: Minimum chunk size (0-888)")
        print("  Lmax: Maximum chunk size (1-888)")
        print("  input_file: Input file path")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    port_str = sys.argv[2]
    Lmin_str = sys.argv[3]
    Lmax_str = sys.argv[4]
    input_file = sys.argv[5]

    # 验证端口号
    try:
        server_port = int(port_str)
        if server_port < 1024 or server_port > 65535:
            print("Error: Port must be between 1024-65535")
            print(f"Current port: {server_port}")
            sys.exit(1)
    except ValueError:
        print("Error: Port must be an integer")
        print(f"Current port: {port_str}")
        sys.exit(1)

    # 验证Lmin和Lmax
    try:
        Lmin = int(Lmin_str)
        Lmax = int(Lmax_str)
        
        if Lmin < 0:
            print("Error: Lmin cannot be less than 0")
            print(f"Current Lmin: {Lmin}")
            sys.exit(1)
        
        if Lmax < 1:
            print("Error: Lmax cannot be less than 1")
            print(f"Current Lmax: {Lmax}")
            sys.exit(1)
        
        if Lmin > Lmax:
            print("Error: Lmin cannot be greater than Lmax")
            print(f"Current Lmin: {Lmin}, Lmax: {Lmax}")
            sys.exit(1)
        
        if Lmax > 888:
            print("Error: Lmax cannot be greater than 888")
            print(f"Current Lmax: {Lmax}")
            sys.exit(1)
    except ValueError:
        print("Error: Lmin and Lmax must be integers")
        print(f"Current Lmin: {Lmin_str}, Lmax: {Lmax_str}")
        sys.exit(1)

    # 验证IP地址 - 使用与UDP客户端相同的正则表达式
    # 允许的特殊地址
    special_addresses = ['localhost', '127.0.0.1']
    
    if server_ip in special_addresses:
        # 特殊地址直接通过
        pass
    else:
        # 使用正则表达式验证IP地址格式
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(ip_pattern, server_ip):
            print("Error: Invalid server IP address format")
            print(f"Current IP: {server_ip}")
            print("Supported formats:")
            print("  - Special addresses: localhost, 127.0.0.1")
            print("  - IPv4 addresses: e.g. 192.168.1.1")
            sys.exit(1)
    
    #文件路径的简单检查
    if not re.match(r"^[\w\-\./]+$", input_file):
        print("Error: Invalid input file path format")
        print(f"Current path: {input_file}")
        print("Supported format: letters, numbers, underscore, hyphen, dot, slash")
        sys.exit(1)
    
    #读取输入文件
    try:
        with open(input_file, 'r') as f:
            data = f.read()
        data_len = len(data)
        print(f"Successfully read input file: {input_file}")
        print(f"File size: {data_len} characters")
    except FileNotFoundError:
        print("Error: Input file not found")
        print(f"File path: {input_file}")
        sys.exit(1)
    except PermissionError:
        print("Error: No permission to read input file")
        print(f"File path: {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read input file: {e}")
        print(f"File path: {input_file}")
        sys.exit(1)

    print(f"Starting TCP client...")
    print(f"Server address: {server_ip}:{server_port}")
    print(f"Chunk range: {Lmin}-{Lmax} characters")
    print(f"Input file: {input_file}")

    #分块
    chunks=[]
    start=0
    while(start<data_len):
        chunk_len=min(random.randint(Lmin,Lmax),data_len-start)
        chunks.append(data[start:start+chunk_len])
        start+=chunk_len
    chunks_num=len(chunks)
    print(f"Data chunking completed, {chunks_num} chunks total")

    #创建TCP连接
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.connect((server_ip,server_port))
        print(f"Successfully connected to server {server_ip}:{server_port}")
    except ConnectionRefusedError:
        print("Error: Connection refused")
        print(f"Please check if server {server_ip}:{server_port} is running")
        sys.exit(1)
    except socket.timeout:
        print("Error: Connection timeout")
        print(f"Please check if server {server_ip}:{server_port} is reachable")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to connect to server: {e}")
        sys.exit(1)

    #发送数据 显示抛出异常
    try:
        # 发送Initialization报文
        init_header=struct.pack('>HI',1,chunks_num)
        sock.sendall(init_header)
        print("Sent initialization packet")

        # 接收Agree报文
        agree_header = sock.recv(6)
        if len(agree_header) < 6:
            raise RuntimeError("Incomplete agree header")
        a_type, a_length = struct.unpack('>HI', agree_header)
        if a_type != 2 or a_length != 0:
            raise RuntimeError("Invalid agree packet")
        print("Received server agreement packet")
        
        #测试多线程效果
        #time.sleep(5)

        # 发送并接收各数据块
        reversed_chunks = []
        for i, chunk in enumerate(chunks):
            # 发送ReverseRequest
            req_header = struct.pack('>HI', 3, len(chunk))
            sock.sendall(req_header + chunk.encode('ascii'))
            
            # 接收ReverseAnswer
            ans_header = sock.recv(6)
            if len(ans_header) < 6:
                raise RuntimeError("Incomplete answer header")
            a_type, a_length = struct.unpack('>HI', ans_header)
            if a_type != 4:
                raise RuntimeError("Invalid answer type")
            reversed_data = sock.recv(a_length).decode('ascii')
            if len(reversed_data) != a_length:
                raise RuntimeError("Incomplete reversed data")
            
            # 打印并保存结果
            print(f"Chunk {i+1}: {reversed_data}")
            print(f"Chunk {i+1} reversed data length: {a_length}")
            reversed_chunks.append(reversed_data)
        #反转数据块顺序使文件符合预期
        reversed_chunks = reversed_chunks[::-1]
        # 生成最终反转文件
        output_file = os.path.splitext(input_file)[0] + "_reversed.txt"
        reversed_chunks
        full_reversed = ''.join(reversed_chunks)
        with open(output_file, 'w') as f:
            f.write(full_reversed)
        print(f"Final reversed file saved to {output_file}")
    except Exception as e:
        print(f"Error during data transmission: {e}")
    finally:
        sock.close()
        print("Connection closed")


if __name__ == '__main__':
    main()