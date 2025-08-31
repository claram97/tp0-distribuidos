import csv
import socket
import logging

from common.utils import Bet, store_bets
from common.communication import Communication, accept_new_connection, send_message
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

    def __store_bets_and_finish(self, client_sock):
        logging.info("action: receive_fin | result: success")
        response = "ACK_FIN\n"
        client_sock.sendall(response.encode())
        logging.info("action: send_ack_fin | result: success")


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
        
    def __decode_and_store_bets(self, bets):
        valid_bets = []
        for idx, bet in enumerate(bets):
            if not bet: # Saltear strings vacíos si los hubiera
                continue
            status, info, data = decode_message(bet)
            if status != "success":
                if "longitud del mensaje recibido no es correcta" in info:
                    logging.error(f"action: invalid_length | result: fail | batch_index: {idx} | raw_bet: '{bet}' | detalle: {info}")
                logging.error(f"action: decode_bet | result: fail | batch_index: {idx} | error: {info} | raw_bet: '{bet}'")
                return f"decode_error: {info}"
            if data is None:
                logging.error(f"action: decode_bet | result: fail | batch_index: {idx} | error: data is None | raw_bet: '{bet}'")
                return "decode_error: data is None"
            
            # Crear objeto Bet y agregarlo a la lista
            bet_obj = Bet(
                agency=data["CLIENT_ID"],
                first_name=data["NOMBRE"],
                last_name=data["APELLIDO"],
                document=data["DOCUMENTO"],
                birthdate=data["NACIMIENTO"],
                number=data["NUMERO"]
            )
            valid_bets.append(bet_obj)
        
        # Almacenar todas las apuestas válidas del batch
        if valid_bets:
            store_bets(valid_bets)
        
        return None

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
                    self.__store_bets_and_finish(client_sock)
                    break
                
                # --- LÓGICA DE DECODIFICACIÓN DE BATCH ACTUALIZADA ---
                bets, batch_error = self.__decode_batch(msg)
                
                if batch_error:
                    logging.error(f"action: decode_batch | result: fail | error: {batch_error}")
                    break
                
                decode_error = self.__decode_and_store_bets(bets)
                
                if decode_error:
                    # Hubo error al decodificar una apuesta dentro del lote
                    logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
                    response = "BATCH_ERROR\n"
                    client_sock.sendall(response.encode())
                    logging.info(f"action: send_error_batch | result: fail | reason: {decode_error}")
                    break
                else:
                    # Todo el lote se procesó correctamente
                    logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
                    logging.info(f"action: batch_processed | result: success | bets_received: {len(bets)}")
                    response = "ACK_BATCH\n"
                    client_sock.sendall(response.encode())
                    logging.info(f"action: send_ack_batch | result: success | bets_received: {len(bets)}")

        finally:
            client_sock.close()
            logging.info("action: connection_closed | result: success")

    def stop(self):
        self._server_socket.close()
        for client_socket in self._client_connections:
            client_socket.close()
            logging.info("action: exit | result: success")

        self._client_connections.clear()
        logging.info("action: exit | result: success")

