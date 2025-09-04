import csv
import socket
import logging

from common.utils import Bet, store_bets
from common.communication import Connection, accept_new_connection
from common.communicationUtils import decode_batch, decode_bets_in_batch, decode_message, encode_message


class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._client_connections = {}

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
        Mantiene la conexión con un cliente usando la clase Connection.
        """
        reader = Connection(client_sock)

        try:
            while True:
                msg, err = reader.read_message()
                if err:
                    logging.error(f"action: receive_message | result: fail | error: {err}")
                    break
                if msg is None:
                    logging.info("action: client_disconnected_unexpectedly | result: success")
                    break

                if msg == "FIN":
                    response = "ACK_FIN\n".encode()
                    reader.send_message(response)
                    logging.info("action: send_ack_fin | result: success")
                    break

                bets, batch_error = decode_batch(msg)
                if batch_error:
                    logging.error(f"action: decode_batch | result: fail | error: {batch_error}")
                    reader.send_message("BATCH_ERROR\n".encode())
                    break

                valid_bets, decode_error = decode_bets_in_batch(bets, client_sock, self._client_connections)
                if decode_error:
                    logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
                    reader.send_message("BATCH_ERROR\n".encode())
                    logging.info(f"action: send_error_batch | result: fail | reason: {decode_error}")
                    break

                if valid_bets:
                    store_bets(valid_bets)

                logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(valid_bets)}")
                reader.send_message("ACK_BATCH\n".encode())
                logging.info(f"action: send_ack_batch | result: success | bets_received: {len(valid_bets)}")


        finally:
            reader.close()
            logging.info("action: connection_closed | result: success")


    def stop(self):
        self._server_socket.close()
        for client_socket in self._client_connections.values():
            client_socket.close()
            logging.info("action: exit | result: success")

        self._client_connections.clear()
        logging.info("action: exit | result: success")

