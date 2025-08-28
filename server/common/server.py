import socket
import logging

from common.utils import Bet, store_bets
from common.communication import accept_new_connection, read_message, send_message
from common.communicationUtils import decode_message, encode_message


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
            client_sock = accept_new_connection(self._server_socket)
            self.__handle_client_connection(client_sock)
        
    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            msg, err = read_message(client_sock)
            if err is not None:
                logging.error(f"action: receive_message | result: fail | error: {err}")
                return

            status, info, data = decode_message(msg)

            addr = client_sock.getpeername()
            logging.info(f'action: receive_message | result: success | ip: {addr[0]}')

            if status == "success":
                store_bets([Bet(
                    agency=int(data["client_id"]),
                    first_name=data["nombre"],
                    last_name=data["apellido"],
                    document=data["documento"],
                    birthdate=data["nacimiento"],
                    number=data["numero"]
                )])

            logging.info(f'action: apuesta_almacenada | result: success | dni: {data["documento"]} | numero: {data["numero"]}.')
            response_bytes = encode_message(status, info)
            send_message(client_sock, response_bytes)
            self._client_connections.append(client_sock)
        except OSError as e:
            logging.error("action: receive_message | result: fail | error: {e}")
        finally:
            if client_sock in self._client_connections:
                self._client_connections.remove(client_sock)
            client_sock.close()

    def stop(self):
        self._server_socket.close()
        for client_socket in self._client_connections:
            client_socket.close()
            logging.info("action: exit | result: success")

        self._client_connections.clear()
        logging.info("action: exit | result: success")

        