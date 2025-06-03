import sys     
import re
import random
import struct
import socket
import os
#import time

def main():
    #检查参数个数和读取参数
    if(len(sys.argv) != 6):
        print("Usage: python reversetcpclient.py <server_ip> <server_port> <Lmin> <Lmax> <input_file>")
        sys.exit(1)
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    Lmin = int(sys.argv[3])
    Lmax = int(sys.argv[4])
    input_file = sys.argv[5]

    #IPv4 地址的正则表达式
    ip_pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    if not re.match(ip_pattern, server_ip):
        print("Invalid server_ip")
        sys.exit(1)

    #端口号的简单检查
    if server_port < 1 or server_port > 65535:
        print("Invalid server_port")
        sys.exit(1)

    #Lmin和Lmax的简单检查 分块设置不大于888不小于0
    if Lmin < 0 or Lmax < 1 or Lmin > Lmax or Lmax>888:
        print("Invalid Lmin or Lmax")
        sys.exit(1)
    
    #文件路径的简单检查
    if not re.match(r"^[\w\-\./]+$", input_file):
        print("Invalid input_file path")
        sys.exit(1)
    
    #读取输入文件
    try:
        with open(input_file, 'r') as f:
            data = f.read()
        data_len = len(data)
    except FileNotFoundError:
        print("Input file not found")
        sys.exit(1)

    #分块
    chunks=[]
    start=0
    while(start<data_len):
        chunk_len=min(random.randint(Lmin,Lmax),data_len-start)
        chunks.append(data[start:start+chunk_len])
        start+=chunk_len
    chunks_num=len(chunks)

    #创建TCP连接
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.connect((server_ip,server_port))

    #发送数据 显示抛出异常
    try:
        # 发送Initialization报文
        init_header=struct.pack('>HI',1,chunks_num)
        sock.sendall(init_header)

        # 接收Agree报文
        agree_header = sock.recv(6)
        if len(agree_header) < 6:
            raise RuntimeError("Incomplete agree header")
        a_type, a_length = struct.unpack('>HI', agree_header)
        if a_type != 2 or a_length != 0:
            raise RuntimeError("Invalid agree packet")
        
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
            print(f"第{i+1}块: {reversed_data}")
            print(f"第{i+1}块反转报文数据部分长度：{a_length}")
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
    finally:
        sock.close()


if __name__ == '__main__':
    main()