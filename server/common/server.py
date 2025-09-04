import socket
import logging
import threading

# collections.defaultdict ya no es necesario aquí
# from collections import defaultdict

from common.utils import has_won, load_bets, store_bets
from common.communication import Connection, accept_new_connection
from common.communicationUtils import decode_batch, decode_bets_in_batch, decode_message, encode_message


class Server:
    def __init__(self, port, listen_backlog, clients_number):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)

        self._clients_number = clients_number
        self._client_connections = {}

        self._client_connections_lock = threading.Lock()
        self._bets_lock = threading.Lock()
        
        self._barrier = threading.Barrier(self._clients_number)


    def run(self):
        """
        Server loop that accepts new connections and handles them in separate threads.
        """
        threads = []
        for _ in range(self._clients_number):
            client_sock, addr = accept_new_connection(self._server_socket)
            logging.info(f"action: accept_connection | result: success | ip: {addr[0]}")
            thread = threading.Thread(target=self.__handle_client_connection, args=(client_sock,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        
        logging.info("action: all_clients_finished | result: success | msg: Server shutting down.")

    def _send_results_to_client(self, client_id, client_sock):
        """
        --- MODIFICADO ---
        Lee el archivo de apuestas completo y envía ("streamea") los resultados
        que pertenecen a este cliente específico a medida que los encuentra.
        """
        logging.info(f"action: send_results | result: in_progress | client_id: {client_id}")
        
        with self._bets_lock:
            bets = load_bets()

        winners_found = 0
        for bet in bets:
            if has_won(bet) and int(bet.agency) == client_id:
                response = f"WINNER|{bet.first_name}|{bet.last_name}|{bet.number}\n"
                Connection(client_sock).send_message(response.encode())
                winners_found += 1
                logging.info(f"action: notify_winner | result: success | client_id: {client_id}")

        logging.info(f"action: finished_streaming_results | result: success | client_id: {client_id} | winners_sent: {winners_found}")

        response = "ACK_FIN\n"
        Connection(client_sock).send_message(response.encode())
        logging.info(f"action: send_ack_fin | result: success | client_id: {client_id}")

        msg, err = Connection(client_sock).read_message()
        if err or msg is None:
            logging.error(f"action: receive_ack_fin | result: fail | client_id: {client_id} | error: {err or 'disconnected'}")
        elif "ACK_FIN" in msg:
            logging.info(f"action: ack_fin_received | result: success | client_id: {client_id}")
        
        with self._client_connections_lock:
            if client_id in self._client_connections:
                del self._client_connections[client_id]
        client_sock.close()


    def __handle_client_connection(self, client_sock):
        """
        Handles the connection for a single client. This code remains mostly the same.
        """
        reader = Connection(client_sock)
        client_id = None

        try:
            while True:
                msg, err = reader.read_message()
                if err or msg is None:
                    log_msg = "client_disconnected_unexpectedly" if msg is None else "receive_message_error"
                    logging.warning(f"action: {log_msg} | result: fail | client_id: {client_id} | error: {err}")
                    break
                
                if msg.strip() == "FIN":
                    logging.info(f"action: client_sent_fin | result: success | client_id: {client_id}")
                    break
                
                bets, batch_error = decode_batch(msg)

                if client_id is None and bets:
                    _, _, data = decode_message(bets[0])
                    if data and "CLIENT_ID" in data:
                        client_id = int(data["CLIENT_ID"])
                        with self._client_connections_lock:
                            self._client_connections[client_id] = client_sock
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
                    response = "ACK_BATCH\n"
                    Connection(client_sock).send_message(response.encode())
        
        finally:
            logging.info(f"action: client_finished_betting | result: success | client_id: {client_id} | msg: Waiting at the barrier.")
            try:
                self._barrier.wait()
            except threading.BrokenBarrierError:
                logging.error("action: barrier_broken | result: fail | msg: A client disconnected prematurely.")
            else:
                if client_id is not None:
                    self._send_results_to_client(client_id, client_sock)
    
    def stop(self):
        """
        Stops the server and closes all connections. No changes here.
        """
        try:
            self._server_socket.close()
        except OSError as e:
            logging.error(f"action: stop_server_socket | result: fail | error: {e}")
        
        with self._client_connections_lock:
            for client_socket in self._client_connections.values():
                try:
                    client_socket.close()
                except OSError as e:
                    logging.error(f"action: stop_client_socket | result: fail | error: {e}")
            self._client_connections.clear()
        
        logging.info("action: server_stopped | result: success")