import logging
from common.utils import Bet

def parse_message(splitted_msg):
    len_str = splitted_msg[0].split('=')[1]
    nombre = splitted_msg[1].split('=')[1]
    apellido = splitted_msg[2].split('=')[1]
    documento = splitted_msg[3].split('=')[1]
    nacimiento = splitted_msg[4].split('=')[1]
    numero = splitted_msg[5].split('=')[1]
    client_id = splitted_msg[6].split('=')[1]
    msg_id = splitted_msg[7].split('=')[1]
    end = splitted_msg[8]
    return len_str, nombre, apellido, documento, nacimiento, numero, client_id, msg_id, end

def decode_message(message):
    """
    Decodifica y valida un mensaje separando primero el encabezado del payload.
    Ahora valida la longitud en CARACTERES.
    """
    try:
        parts = message.split('|', 1)
        if len(parts) != 2:
            return "failed", "el formato del mensaje es inválido (no se encontró 'LEN|payload')", None

        header, payload = parts
        
        if not header.startswith("LEN="):
            return "failed", "el encabezado no comienza con 'LEN='", None
        
        try:
            len_value_str = header.split('=')[1]
            expected_len = int(len_value_str)
        except (IndexError, ValueError):
            return "failed", "el valor de LEN en el encabezado es inválido", None

        if len(payload) != expected_len:
            return "failed", f"la longitud del payload no coincide (esperada: {expected_len}, real: {len(payload)})", None

        splitted_payload = payload.split('|')
        if not splitted_payload or splitted_payload[-1] != 'END':
            return "failed", "el payload no termina con el marcador 'END'", None

        fields_to_process = splitted_payload[:-1]

        if len(fields_to_process) != 7:
            return "failed", f"el payload no tiene los 7 campos KEY=VALUE esperados", None

        data = {}
        for field in fields_to_process:
            key_value = field.split('=', 1)
            if len(key_value) != 2:
                return "failed", f"el campo '{field}' no tiene el formato KEY=VALUE", None
            key, value = key_value
            data[key.strip()] = value.strip()

        documento = data.get("DOCUMENTO")
        if not documento or len(documento) != 8 or not documento.isdigit():
            return "failed", "el documento debe tener 8 dígitos", None
        
        return "success", "none", data

    except Exception as e:
        return "failed", f"error inesperado al procesar el mensaje: {e}", None
    
def encode_message(status, info):
    response_body = f"STATUS={status}|INFO={info}|END\n"
    response = f"LEN={len(response_body)}|{response_body}"

    return response.encode('utf-8')

def decode_batch(batch_message):
    """
    Decodifica y valida un lote completo (batch).
    Separa el encabezado del payload, valida la longitud en CARACTERES y extrae las apuestas.
    """
    try:
        parts = batch_message.split('|', 1)
        if len(parts) != 2:
            return None, "Formato de batch inválido (no se encontró 'BATCH_LEN|payload')"

        header, payload = parts

        if not header.startswith("BATCH_LEN="):
            return None, "El encabezado del batch no comienza con 'BATCH_LEN='"
        
        len_value_str = header.split('=')[1]
        expected_len = int(len_value_str)

        if len(payload) + 1 != expected_len:
            error_msg = f"La longitud del payload del batch no coincide (esperada: {expected_len}, real: {len(payload) + 1})"
            return None, error_msg

        footer = "|END_BATCH"
        if not payload.endswith(footer):
            return None, "El payload del batch no termina con el footer '|END_BATCH'"
        
        bets_body = payload[:-len(footer)]
        
        individual_bets = [bet for bet in bets_body.split(':') if bet]

        return individual_bets, None

    except (ValueError, IndexError) as e:
        return None, f"Error al parsear el encabezado del batch: {e}"
    except Exception as e:
        return None, f"Error inesperado al decodificar el batch: {e}"

def _register_client(client_id, client_sock, client_connections):
    """
    Registra la conexión de un cliente si es la primera vez que se lo ve.
    """
    if int(client_id) not in client_connections:
        client_connections[int(client_id)] = client_sock
        logging.info(f"action: client_registered | result: success | client_id: {client_id}")

def _create_bet_from_data(data):
    """
    Crea un objeto Bet a partir de un diccionario de datos.
    Lanza KeyError si falta alguna clave esperada en los datos.
    """
    return Bet(
        agency=data["CLIENT_ID"],
        first_name=data["NOMBRE"],
        last_name=data["APELLIDO"],
        document=data["DOCUMENTO"],
        birthdate=data["NACIMIENTO"],
        number=data["NUMERO"]
    )

def decode_bets_in_batch(bets, client_sock, client_connections):
    """
    Decodifica un batch de apuestas orquestando la validación, registro
    de cliente y creación de objetos.
    """
    valid_bets = []
    client_id_registered = False

    for idx, bet_string in enumerate(bets):
        if not bet_string:
            continue

        status, info, data = decode_message(bet_string)
        if status != "success":
            if "longitud del mensaje recibido no es correcta" in info:
                logging.error(
                    f"action: invalid_length | result: fail | batch_index: {idx} "
                    f"| raw_bet: '{bet_string}' | detalle: {info}"
                )
            return None, f"decode_error: {info}"

        if data is None:
            return None, f"decode_error: data is None | raw_bet: '{bet_string}'"

        try:
            if not client_id_registered:
                client_id = data["CLIENT_ID"]
                _register_client(client_id, client_sock, client_connections)
                client_id_registered = True

            bet_obj = _create_bet_from_data(data)
            valid_bets.append(bet_obj)

        except KeyError as e:
            # Este error ocurre si a 'data' le falta una clave como "CLIENT_ID", "NOMBRE", etc.
            logging.error(f"action: create_bet_obj | result: fail | batch_index: {idx} | error: missing key {e}")
            return None, f"decode_error: campo de datos faltante ({e}) en la apuesta {idx}"

    return valid_bets, None