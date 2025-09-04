import csv
import socket
import logging

from common.utils import Bet, has_won, load_bets, store_bets
from common.communication import Connection, accept_new_connection
from common.communicationUtils import decode_batch, decode_bets_in_batch


class Server:
    def __init__(self, port, listen_backlog, clients_number):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._client_connections = {}
        self._clients_list = []
        self._confirmation_count = 0
        self._clients_number = clients_number
        self._current_clients_number = 0

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        while self._current_clients_number < self._clients_number:
            client_sock = accept_new_connection(self._server_socket)
            self._clients_list.append(client_sock)
            self._current_clients_number += 1

        for client_sock in self._clients_list:
            self.__handle_client_connection(client_sock)
        
        for bet in load_bets():
            if has_won(bet):
                logging.info(f"action: winner_found | result: success | winner: {bet.first_name} {bet.last_name} | number: {bet.number} | client_id: {bet.agency}")

                if bet.agency in self._client_connections.keys():
                    logging.info(f"action: notify_winner | result: success | client_id: {bet.agency} | winner: {bet.first_name} {bet.last_name} | number: {bet.number}")
                    response = f"WINNER|{bet.first_name}|{bet.last_name}|{bet.number}\n"
                    client_socket = self._client_connections[bet.agency]
                    Connection(client_socket).send_message(response.encode())

        for (client_id, client_socket) in self._client_connections.items():
            response = "ACK_FIN\n"
            Connection(client_socket).send_message(response.encode())
            logging.info("action: send_ack_fin | result: success")
            datos_recibidos = client_socket.recv(1024)
            if "ACK_FIN" in datos_recibidos.decode():
                client_socket.close()
                logging.info(f"action: ack_fin_received | result: success | client_id: {client_id}")

    def __handle_client_connection(self, client_sock):
        """
        Mantiene la conexión para un diálogo de pregunta-respuesta con el cliente.
        """
        reader = Connection(client_sock)

        try:
            while True:
                msg, err = reader.read_message()
                if err is not None:
                    logging.error(f"action: receive_message | result: fail | error: {err}")
                    break
                if msg is None:
                    logging.info("action: client_disconnected_unexpectedly | result: success")
                    break
                
                if msg == "FIN":
                    break
                
                bets, batch_error = decode_batch(msg)
                if batch_error:
                    logging.error(f"action: decode_batch | result: fail | error: {batch_error}")
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
            logging.info("action: finish_loop | result: success")

    def stop(self):
        self._server_socket.close()
        for client_socket in self._client_connections.values():
            client_socket.close()
            logging.info("action: exit | result: success")

        self._client_connections.clear()
        logging.info("action: exit | result: success")

