import logging

class Connection:
    """
    Clase que maneja un socket TCP:
    - Lectura de mensajes completos delimitados por '\n'
    - Envío de mensajes asegurando que todos los bytes se envíen
    """
    def __init__(self, sock):
        self.sock = sock
        self.buffer = b""

    def read_message(self):
        """
        Lee del socket hasta encontrar un mensaje completo.
        Devuelve el mensaje como str. Guarda datos sobrantes en buffer.
        """
        while b"\n" not in self.buffer:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    if self.buffer:
                        logging.warning(
                            "action: read_message | result: fail | error: connection closed with incomplete message"
                        )
                        return None, RuntimeError("Connection closed with incomplete message")
                    return None, None 
                self.buffer += chunk
            except OSError as e:
                return None, RuntimeError(f"recv_error: {e}")

        delimiter_pos = self.buffer.find(b"\n")
        message_bytes = self.buffer[:delimiter_pos]
        self.buffer = self.buffer[delimiter_pos + 1:]

        try:
            return message_bytes.decode("utf-8"), None
        except UnicodeDecodeError as e:
            return None, RuntimeError(f"decode_error: {e}")

    def send_message(self, data: bytes):
        """
        Envía todos los bytes del mensaje a través del socket.
        """
        total_sent = 0
        while total_sent < len(data):
            try:
                sent = self.sock.send(data[total_sent:])
                if sent == 0:
                    raise RuntimeError("Socket connection broken")
                total_sent += sent
            except OSError as e:
                raise RuntimeError(f"send_error: {e}")

    def close(self):
        self.sock.close()

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