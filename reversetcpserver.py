import socket
import sys
import threading
import struct
import re

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
        print("Error: Invalid number of arguments")
        print("Usage: python reversetcpserver.py <port>")
        print("Example: python reversetcpserver.py 8888")
        print("Parameters:")
        print("  port: Server port (1024-65535)")
        sys.exit(1)
    
    port_str = sys.argv[1]
    
    # 验证端口号
    try:
        port = int(port_str)
        if port < 1024 or port > 65535:
            print("Error: Port must be between 1024-65535")
            print(f"Current port: {port}")
            sys.exit(1)
    except ValueError:
        print("Error: Port must be an integer")
        print(f"Current port: {port_str}")
        sys.exit(1)

    print(f"Starting TCP server...")
    print(f"Listening port: {port}")

    #创建TCP服务器
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #设置端口复用
        server_socket.bind(('172.31.53.98', port))
        server_socket.listen(5)
        print(f"Server started successfully, listening on port {port}...")
        print("Waiting for client connections...")
    except PermissionError:
        print("Error: No permission to bind port")
        print(f"Port: {port}")
        print("Try using a higher port number or run with administrator privileges")
        sys.exit(1)
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print("Error: Port already in use")
            print(f"Port: {port}")
            print("Try using a different port number")
        else:
            print(f"Error: Failed to bind port: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to start server: {e}")
        sys.exit(1)

    try:
        while True:
            conn, addr = server_socket.accept()
            #添加新线程
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server runtime error: {e}")
    finally:
        server_socket.close()
        print("Server closed")

if __name__ == '__main__':
    main()