import csv
import socket
import logging

from common.utils import Bet, has_won, load_bets, store_bets
from common.communication import Communication, accept_new_connection, send_message
from common.communicationUtils import decode_batch, decode_message, encode_message


class Server:
    def __init__(self, port, listen_backlog, clients_number):
        # Initialize server socket
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
            client_sock, addr = accept_new_connection(self._server_socket)
            self._clients_list.append(client_sock)
            self._current_clients_number += 1

        for client_sock in self._clients_list:
            self.__handle_client_connection(client_sock)
        
        for bet in load_bets():
            if has_won(bet):
                logging.info(f"action: winner_found | result: success | winner: {bet.first_name} {bet.last_name} | number: {bet.number} | client_id: {bet.agency}")
                # Notificar los ganadores a través de su conexión guardada

                if bet.agency in self._client_connections.keys():
                    logging.info(f"action: notify_winner | result: success | client_id: {bet.agency} | winner: {bet.first_name} {bet.last_name} | number: {bet.number}")
                    response = f"WINNER|{bet.first_name}|{bet.last_name}|{bet.number}\n"
                    client_socket = self._client_connections[bet.agency]
                    client_socket.sendall(response.encode())

        for (client_id, client_socket) in self._client_connections.items():
            response = "ACK_FIN\n"
            client_socket.sendall(response.encode())
            logging.info("action: send_ack_fin | result: success")
            datos_recibidos = client_socket.recv(1024)
            if "ACK_FIN" in datos_recibidos.decode():
                client_socket.close()
                logging.info(f"action: ack_fin_received | result: success | client_id: {client_id}")

    def __decode_batch(self, batch_message):
        """
        Decodifica y valida un lote completo (batch).
        Separa el encabezado del payload, valida la longitud en CARACTERES y extrae las apuestas.
        """
        try:
            # 1. Separar encabezado del payload del lote
            parts = batch_message.split('|', 1)
            if len(parts) != 2:
                return None, "Formato de batch inválido (no se encontró 'BATCH_LEN|payload')"

            header, payload = parts

            # 2. Validar el encabezado y la longitud del payload en CARACTERES
            if not header.startswith("BATCH_LEN="):
                return None, "El encabezado del batch no comienza con 'BATCH_LEN='"
            
            len_value_str = header.split('=')[1]
            expected_len = int(len_value_str)

            # --- LÓGICA CORREGIDA PARA CARACTERES ---
            # Comparamos la cantidad de caracteres. Sumamos 1 por el '\n' que el reader quita.
            if len(payload) + 1 != expected_len:
                error_msg = f"La longitud del payload del batch no coincide (esperada: {expected_len}, real: {len(payload) + 1})"
                return None, error_msg

            # 3. Quitar el footer '|END_BATCH' del payload
            # El '\n' ya fue quitado por el reader, así que buscamos el footer sin él.
            footer = "|END_BATCH"
            if not payload.endswith(footer):
                return None, "El payload del batch no termina con el footer '|END_BATCH'"
            
            bets_body = payload[:-len(footer)]
            
            # 4. Separar las apuestas individuales
            # Filtramos para quitar el último elemento si queda vacío por el ':' final
            individual_bets = [bet for bet in bets_body.split(':') if bet]

            return individual_bets, None

        except (ValueError, IndexError) as e:
            return None, f"Error al parsear el encabezado del batch: {e}"
        except Exception as e:
            return None, f"Error inesperado al decodificar el batch: {e}"
        
    def decode_and_collect_bets(self, bets, client_sock):
        """
        Decodifica un batch de apuestas y devuelve la lista de Bet válidas.
        Si alguna apuesta es inválida, lanza un error retornando el motivo.
        """
        valid_bets = []
        client_id = None

        for idx, bet in enumerate(bets):
            if not bet:
                continue

            status, info, data = decode_message(bet)
            if status != "success":
                if "longitud del mensaje recibido no es correcta" in info:
                    logging.error(
                        f"action: invalid_length | result: fail | batch_index: {idx} "
                        f"| raw_bet: '{bet}' | detalle: {info}"
                    )
                return None, f"decode_error: {info}"

            if data is None:
                return None, f"decode_error: data is None | raw_bet: '{bet}'"

            # Registrar client_id si es la primera apuesta válida
            if client_id is None:
                client_id = data["CLIENT_ID"]
                if client_id not in self._client_connections:
                    self._client_connections[int(client_id)] = client_sock
                    logging.info(f"action: client_registered | result: success | client_id: {client_id}")

            # Crear objeto Bet
            bet_obj = Bet(
                agency=data["CLIENT_ID"],
                first_name=data["NOMBRE"],
                last_name=data["APELLIDO"],
                document=data["DOCUMENTO"],
                birthdate=data["NACIMIENTO"],
                number=data["NUMERO"]
            )
            valid_bets.append(bet_obj)

        return valid_bets, None


    def __handle_client_connection(self, client_sock):
        """
        Mantiene la conexión para un diálogo de pregunta-respuesta con el cliente.
        """
        reader = Communication(client_sock)

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
                    # self.__store_bets_and_finish(client_sock)
                    break
                
                # --- LÓGICA DE DECODIFICACIÓN DE BATCH ACTUALIZADA ---
                bets, batch_error = decode_batch(msg)
                if batch_error:
                    logging.error(f"action: decode_batch | result: fail | error: {batch_error}")
                    break

                valid_bets, decode_error = self.decode_and_collect_bets(bets, client_sock)
                if decode_error:
                    logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
                    client_sock.sendall("BATCH_ERROR\n".encode())
                    logging.info(f"action: send_error_batch | result: fail | reason: {decode_error}")
                    break

                # Solo si todo se decodificó bien, almacenamos las apuestas
                if valid_bets:
                    store_bets(valid_bets)

                logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(valid_bets)}")
                client_sock.sendall("ACK_BATCH\n".encode())
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

