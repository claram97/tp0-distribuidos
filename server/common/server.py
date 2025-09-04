import socket
import logging

from common.utils import Bet, store_bets
from common.communication import accept_new_connection, Connection
from common.communicationUtils import decode_message, encode_message

class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._client_connections = []

    def run(self):
        """
        Loop principal del servidor.
        Acepta nuevas conexiones y maneja cada cliente.
        """
        while True:
            client_sock = accept_new_connection(self._server_socket)
            self.__handle_client_connection(client_sock)

    def __handle_client_connection(self, client_sock):
        """
        Maneja la comunicación con un cliente usando Connection.
        """
        conn = Connection(client_sock)
        try:
            msg, err = conn.read_message()
            if err:
                logging.error(f"action: receive_message | result: fail | error: {err}")
                return
            if msg is None:
                logging.info("action: client_disconnected_unexpectedly | result: success")
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
            conn.send_message(response_bytes)

            # Guardar conexión activa
            self._client_connections.append(conn)

        except OSError as e:
            logging.error(f"action: receive_message | result: fail | error: {e}")
        finally:
            if conn in self._client_connections:
                self._client_connections.remove(conn)
            conn.close()
            logging.info("action: connection_closed | result: success")

    def stop(self):
        self._server_socket.close()
        for conn in self._client_connections:
            conn.close()
            logging.info("action: exit | result: success")
        self._client_connections.clear()
        logging.info("action: exit | result: success")
