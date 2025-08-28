import logging


def read_message(client_sock):
    buffer = b""
    try:
        while True:
            chunk = client_sock.recv(1024)
            if not chunk:
                if not buffer:
                    return None, RuntimeError("socket closed by peer")
                break
            buffer += chunk
            if b"\n" in chunk:
                break

        try:
            msg = buffer.decode("utf-8").strip()
            return msg, None
        except UnicodeDecodeError as e:
            return None, RuntimeError(f"decode_error: {e}")
    except OSError as e:
            return None, RuntimeError(f"recv_error: {e}")

def send_message(client_sock, response_bytes):
    total_sent = 0
    while total_sent < len(response_bytes):
        sent = client_sock.send(response_bytes[total_sent:])
        if sent == 0:
            raise RuntimeError("Socket connection broken")
        total_sent += sent

def accept_new_connection(server_socket):
    """
    Accept new connections

    Function blocks until a connection to a client is made.
    Then connection created is printed and returned
    """

    logging.info('action: accept_connections | result: in_progress')
    c, addr = server_socket.accept()
    logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
    return c