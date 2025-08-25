import socket
import logging

from common.utils import Bet, store_bets


class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._client_connections = []

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """

        # TODO: Modify this program to handle signal to graceful shutdown
        # the server
        while True:
            client_sock = self.__accept_new_connection()
            self.__handle_client_connection(client_sock)

    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            buffer = b""
            while True:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                if b"\n" in chunk:
                    break
            msg = buffer.decode('utf-8').strip()
            
            # TODO: función para decodificar el mensaje
            splitted_msg = msg.split('|')
            if len(splitted_msg) == 9:

                len_str = splitted_msg[0].split('=')[1]
                nombre = splitted_msg[1].split('=')[1]
                apellido = splitted_msg[2].split('=')[1]
                documento = splitted_msg[3].split('=')[1]
                nacimiento = splitted_msg[4].split('=')[1]
                numero = splitted_msg[5].split('=')[1]
                client_id = splitted_msg[6].split('=')[1]
                msg_id = splitted_msg[7].split('=')[1]
                end = splitted_msg[8]
                
                # TODO: validar datos
                received_len = len(splitted_msg[1]) + len(splitted_msg[2]) + len(splitted_msg[3]) + len(splitted_msg[4]) + len(splitted_msg[5]) + len(splitted_msg[6]) + len(splitted_msg[7]) + len(splitted_msg[8]) + 8
                if int(len_str) != received_len:
                    status='failed'
                    info='la longitud del mensaje recibido no es correcta'
                # TODO: agregar las validaciones acá
                else:
                    status='success'
                    info='none'
            else:
                status='failed'
                info='el mensaje recibido no tiene el formato esperado'
            
            addr = client_sock.getpeername()
            logging.info(f'action: receive_message | result: success | ip: {addr[0]} | msg: {splitted_msg}')

            # Log pedido por consigna
            store_bets([Bet(agency=1, first_name=nombre, last_name=apellido, document=documento, birthdate=nacimiento, number=numero)])
            logging.info(f'action: apuesta_almacenada | result: success | dni: {documento} | numero: {numero}.')
            response_body = f"STATUS={status}|INFO={info}|END\n"
            response = f"LEN={len(response_body)}|{response_body}"

            response_bytes = response.encode('utf-8')
            total_sent = 0
            while total_sent < len(response_bytes):
                sent = client_sock.send(response_bytes[total_sent:])
                if sent == 0:
                    raise RuntimeError("Socket connection broken")
                total_sent += sent

            self._client_connections.append(client_sock)
        except OSError as e:
            logging.error("action: receive_message | result: fail | error: {e}")
        finally:
            if client_sock in self._client_connections:
                self._client_connections.remove(client_sock)
            client_sock.close()

    def __accept_new_connection(self):
        """
        Accept new connections

        Function blocks until a connection to a client is made.
        Then connection created is printed and returned
        """

        # Connection arrived
        logging.info('action: accept_connections | result: in_progress')
        c, addr = self._server_socket.accept()
        logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
        return c

    def stop(self):
        self._server_socket.close()
        for client_socket in self._client_connections:
            client_socket.close()
            logging.info("action: exit | result: success")

        self._client_connections.clear()
        logging.info("action: exit | result: success")

        