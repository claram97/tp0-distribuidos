import socket
import logging

from common.utils import Bet, store_bets
from common.communication import read_message
from common.communicationUtils import decode_message


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

    def __read_message(self, client_sock):
        buffer = b""
        try:
            while True:
                chunk = client_sock.recv(1024)
                if not chunk:
                    # conexión cerrada por el cliente
                    if not buffer:
                        return None, RuntimeError("socket closed by peer")
                    break
                buffer += chunk
                if b"\n" in chunk:
                    break

            try:
                msg = buffer.decode("utf-8").strip()
                return msg, None
            except UnicodeDecodeError as e:
                return None, RuntimeError(f"decode_error: {e}")

        except OSError as e:
            return None, RuntimeError(f"recv_error: {e}")

    def __validate_data(self):
        return True
        
    def __decode_message(self, message):
        try:
            if len(message) != 9:
                return "failed", "el mensaje recibido no tiene el formato esperado", None

            try:
                len_str = message[0].split('=')[1]
                nombre = message[1].split('=')[1]
                apellido = message[2].split('=')[1]
                documento = message[3].split('=')[1]
                nacimiento = message[4].split('=')[1]
                numero = message[5].split('=')[1]
                client_id = message[6].split('=')[1]
                msg_id = message[7].split('=')[1]
                end = message[8]
            except (IndexError, ValueError):
                return "failed", "error al parsear los campos del mensaje", None

            # Validar longitud
            try:
                received_len = (
                    len(message[1]) + len(message[2]) + len(message[3]) +
                    len(message[4]) + len(message[5]) + len(message[6]) +
                    len(message[7]) + len(message[8]) + 8
                )
                if int(len_str) != received_len:
                    return "failed", "la longitud del mensaje recibido no es correcta", None
            except ValueError:
                return "failed", "LEN del mensaje no es un entero válido", None

            # TODO: agregar más validaciones según necesites

            # Retornamos los campos parseados en un diccionario
            data = {
                "nombre": nombre,
                "apellido": apellido,
                "documento": documento,
                "nacimiento": nacimiento,
                "numero": numero,
                "client_id": client_id,
                "msg_id": msg_id,
                "end": end
            }

            return "success", "none", data

        except Exception:
            return "failed", "el mensaje recibido no tiene el formato esperado", None
        
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
            logging.info(f'action: receive_message | result: success | ip: {addr[0]} | msg: {msg.split('|')}')

            if status == "success":
                store_bets([Bet(
                    agency=1,
                    first_name=data["nombre"],
                    last_name=data["apellido"],
                    document=data["documento"],
                    birthdate=data["nacimiento"],
                    number=data["numero"]
                )])

            logging.info(f'action: apuesta_almacenada | result: success | dni: {data["documento"]} | numero: {data["numero"]}.')
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

        