import logging

class Communication:
    """
    Una clase que maneja la lectura de un socket TCP para asegurar
    que se lean mensajes completos delimitados por un salto de línea ('\n').
    """
    def __init__(self, client_sock):
        self.sock = client_sock
        # Buffer para guardar los datos que se leen del socket.
        self.buffer = b""

    def read_message(self):
        """
        Lee del socket hasta encontrar un mensaje completo.
        Devuelve el mensaje y guarda los datos sobrantes en el buffer.
        """
        # Bucle principal: Sigue leyendo del socket hasta que haya un
        # delimitador ('\n') en nuestro buffer.
        while b"\n" not in self.buffer:
            try:
                # Leemos un chunk de datos del socket. 4096 es un tamaño común.
                chunk = self.sock.recv(4096)
                if not chunk:
                    # El cliente cerró la conexión.
                    # Si el buffer tiene datos, es un mensaje incompleto.
                    if self.buffer:
                        logging.warning("action: read_message | result: fail | error: connection closed with incomplete message")
                        return None, RuntimeError("Connection closed with incomplete message")
                    # Si no hay nada en el buffer, es un cierre limpio.
                    return None, None # Indicador de que la conexión terminó.

                self.buffer += chunk

            except OSError as e:
                # Error de red al intentar leer.
                return None, RuntimeError(f"recv_error: {e}")

        # Si salimos del bucle, es porque tenemos al menos un mensaje en el buffer.
        # Buscamos la posición del primer salto de línea.
        delimiter_pos = self.buffer.find(b"\n")

        # El mensaje es todo lo que está ANTES del salto de línea.
        message_bytes = self.buffer[:delimiter_pos]

        # --- ¡La parte clave! ---
        # Actualizamos el buffer para que contenga solo los datos que venían
        # DESPUÉS del primer mensaje.
        self.buffer = self.buffer[delimiter_pos + 1:]

        try:
            # Decodificamos solo los bytes del mensaje que extrajimos.
            msg = message_bytes.decode("utf-8")
            return msg, None
        except UnicodeDecodeError as e:
            return None, RuntimeError(f"decode_error: {e}")


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
    return c, addr