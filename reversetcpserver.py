import socket
import sys
import threading
import struct

#处理单个线程
def handle_client(conn, addr):
    print(f"New connection from {addr}")
    try:
        # 接收Initialization报文
        init_header = conn.recv(6)
        if len(init_header) < 6:
            print(f"Incomplete initialization header from {addr}")
            return
        i_type, chunks_num = struct.unpack('>HI', init_header)
        if i_type != 1:
            print(f"Invalid initialization type from {addr}")
            return
        
        # 发送Agree报文
        agree_packet = struct.pack('>HI', 2, 0)
        conn.sendall(agree_packet)
        
        # 处理数据块请求
        for _ in range(chunks_num):
            # 接收ReverseRequest
            req_header = conn.recv(6)
            if len(req_header) < 6:
                print(f"Incomplete request header from {addr}")
                break
            r_type, data_len = struct.unpack('>HI', req_header)
            if r_type != 3:
                print(f"Invalid request type from {addr}")
                break
            
            data = b''
            while len(data) < data_len:
                chunk = conn.recv(data_len - len(data))
                if not chunk:
                    break
                data += chunk
            if len(data) != data_len:
                print(f"Incomplete request data from {addr}")
                break
            
            # 反转数据并发送答案
            reversed_str = data.decode('ascii')[::-1]
            ans_header = struct.pack('>HI', 4, len(reversed_str))
            conn.sendall(ans_header + reversed_str.encode('ascii'))
    
    finally:
        conn.close()
        print(f"Connection closed: {addr}")

def main():
    #检查参数个数和读取参数
    if len(sys.argv) != 2:
        print("Usage: python server.py <port>")
        sys.exit(1)
    port = int(sys.argv[1])
    if port < 1 or port > 65535:
        print("Invalid port")
        sys.exit(1)

    #创建TCP服务器
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #设置端口复用
    server_socket.bind(('172.31.53.98', port))
    server_socket.listen(5)
    print(f"Server listening on port {port}...")

    try:
        while True:
            conn, addr = server_socket.accept()
            #添加新线程
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("Server shutting down")
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()