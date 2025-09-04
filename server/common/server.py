import socket
import logging
import threading

from common.utils import has_won, load_bets, store_bets
from common.communication import Connection, accept_new_connection
from common.communicationUtils import decode_batch, decode_bets_in_batch, decode_message, encode_message


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
        self._client_connections_lock = threading.Lock()
        self._bets_lock = threading.Lock()

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        while True:
            client_sock, addr = accept_new_connection(self._server_socket)
            thread = threading.Thread(target=self.__handle_client_connection, args=(client_sock,))
            with self._client_connections_lock:
                self._clients_list.append(client_sock)
            thread.start()

    def _send_winner_numbers(self, client_id):
        with self._bets_lock:
            bets = load_bets()

        with self._client_connections_lock:
            if client_id not in self._client_connections:
                logging.warning(f"action: send_winner_numbers | result: fail | reason: client_id {client_id} not found")
                return
            client_socket = self._client_connections[client_id]

        for bet in bets:
            if has_won(bet):
                if bet.agency == client_id:
                    logging.info(f"action: notify_winner | result: success | client_id: {bet.agency} | winner: {bet.first_name} {bet.last_name} | number: {bet.number}")
                    response = f"WINNER|{bet.first_name}|{bet.last_name}|{bet.number}\n"
                    with self._client_connections_lock:
                        if bet.agency in self._client_connections:
                            client_socket = self._client_connections[bet.agency]
                            Connection(client_socket).send_message(response.encode())

        response = "ACK_FIN\n"
        Connection(client_socket).send_message(response.encode())
        logging.info("action: send_ack_fin | result: success")
        msg, err = Connection(client_socket).read_message()
        if err is not None:
            logging.error(f"action: receive_message | result: fail | error: {err}")
            return
        if msg is None:
            logging.info("action: client_disconnected_unexpectedly | result: success")
            return
        if "ACK_FIN" in msg:
            client_socket.close()
            with self._client_connections_lock:
                if client_id in self._client_connections:
                    del self._client_connections[client_id]
            logging.info(f"action: ack_fin_received | result: success | client_id: {client_id}")

    def __handle_client_connection(self, client_sock):
        """
        Mantiene la conexión para un diálogo de pregunta-respuesta con el cliente.
        """
        reader = Connection(client_sock)
        client_id = None

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
                # Obtener client_id del primer lote recibido
                if client_id is None and bets and len(bets) > 0:
                    first_bet = bets[0]
                    _, _, data = decode_message(first_bet)
                    if data is not None:
                        client_id = data["CLIENT_ID"]
                        if client_id not in self._client_connections:
                            with self._client_connections_lock:
                                self._client_connections[int(client_id)] = client_sock
                            logging.info(f"action: client_registered | result: success | client_id: {client_id}")

                if batch_error:
                    logging.error(f"action: decode_batch | result: fail | error: {batch_error}")
                    break

                decode_error = decode_bets_in_batch(bets, client_sock, self._client_connections, self._client_connections_lock, self._bets_lock)

                if decode_error:
                    logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
                    response = "BATCH_ERROR\n"
                    Connection(client_sock).send_message(response.encode())
                    logging.info(f"action: send_error_batch | result: fail | reason: {decode_error}")
                    break
                else:
                    logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
                    logging.info(f"action: batch_processed | result: success | bets_received: {len(bets)}")
                    response = "ACK_BATCH\n"
                    Connection(client_sock).send_message(response.encode())
                    logging.info(f"action: send_ack_batch | result: success | bets_received: {len(bets)}")

        finally:
            logging.info("action: finish_loop | result: success")
            self._send_winner_numbers(int(client_id))

    def stop(self):
        self._server_socket.close()
        for client_socket in self._client_connections.values():
            client_socket.close()
            logging.info("action: exit | result: success")

        self._client_connections.clear()
        logging.info("action: exit | result: success")

