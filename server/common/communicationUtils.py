import logging
from common.utils import Bet

def parse_message(splitted_msg):
    """
    Parsea una lista de strings con formato 'KEY=VALUE' y extrae los valores.
    """
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

def _split_header_payload(message):
    """
    Separa el mensaje en encabezado y payload.
    Devuelve (header, payload, None) si es exitoso, o (None, None, error_msg) si falla.
    """
    parts = message.split('|', 1)
    if len(parts) != 2:
        return None, None, "el formato del mensaje es inválido (no se encontró 'LEN|payload')"
    return parts[0], parts[1], None

def _validate_header_and_length(header, payload):
    """
    Valida que el header comience con 'LEN=' y que la longitud del payload coincida.
    Devuelve un mensaje de error si falla, o None si es exitoso.
    """
    if not header.startswith("LEN="):
        return "el encabezado no comienza con 'LEN='"
    
    try:
        len_value_str = header.split('=')[1]
        expected_len = int(len_value_str)
    except (IndexError, ValueError):
        return "el valor de LEN en el encabezado es inválido"

    if len(payload) != expected_len:
        return f"la longitud del payload no coincide (esperada: {expected_len}, real: {len(payload)})"
    
    return None

def _parse_payload_fields(payload):
    """
    Parsea los campos KEY=VALUE del payload, valida la estructura y el marcador 'END'.
    Devuelve (data_dict, None) si es exitoso, o (None, error_msg) si falla.
    """
    splitted_payload = payload.split('|')
    if not splitted_payload or splitted_payload[-1] != 'END':
        return None, "el payload no termina con el marcador 'END'"

    fields_to_process = splitted_payload[:-1]
    if len(fields_to_process) != 7:
        return None, "el payload no tiene los 7 campos KEY=VALUE esperados"

    data = {}
    for field in fields_to_process:
        key_value = field.split('=', 1)
        if len(key_value) != 2:
            return None, f"el campo '{field}' no tiene el formato KEY=VALUE"
        key, value = key_value
        data[key.strip()] = value.strip()
    
    return data, None

def _validate_data(data):
    """
    Valida las reglas de negocio específicas de los datos ya parseados.
    Devuelve un mensaje de error si falla, o None si es exitoso.
    """
    documento = data.get("DOCUMENTO")
    if not documento or len(documento) != 8 or not documento.isdigit():
        return "el documento debe tener 8 dígitos"
    
    return None 

def decode_message(message):
    """
    Decodifica y valida un mensaje individual orquestando funciones de validación más pequeñas.
    """
    try:
        header, payload, error = _split_header_payload(message)
        if error:
            return "failed", error, None

        error = _validate_header_and_length(header, payload)
        if error:
            return "failed", error, None

        data, error = _parse_payload_fields(payload)
        if error:
            return "failed", error, None

        error = _validate_data(data)
        if error:
            return "failed", error, None
        
        return "success", "none", data

    except Exception as e:
        return "failed", f"error inesperado al procesar el mensaje: {e}", None
    
def encode_message(status, info):
    """
    Codifica un mensaje de respuesta con un estado y una información,
    calculando y anteponiendo el encabezado de longitud.
    """
    response_body = f"STATUS={status}|INFO={info}|END\n"
    response = f"LEN={len(response_body)}|{response_body}"

    return response.encode('utf-8')


def _split_batch_header_payload(batch_message):
    """
    Separa el mensaje de batch en encabezado y payload.
    Devuelve (header, payload, None) si es exitoso, o (None, None, error_msg) si falla.
    """
    parts = batch_message.split('|', 1)
    if len(parts) != 2:
        return None, None, "Formato de batch inválido (no se encontró 'BATCH_LEN|payload')"
    return parts[0], parts[1], None

def _validate_batch_header_and_length(header, payload):
    """
    Valida el header del batch ('BATCH_LEN=') y que la longitud del payload sea la correcta.
    Devuelve un mensaje de error si falla, o None si es exitoso.
    """
    if not header.startswith("BATCH_LEN="):
        return "El encabezado del batch no comienza con 'BATCH_LEN='"
    
    try:
        len_value_str = header.split('=')[1]
        expected_len = int(len_value_str)
    except (IndexError, ValueError) as e:
        return f"Error al parsear el encabezado del batch: {e}"

    # Se suma 1 a la longitud real para contar el primer separador '|'
    if len(payload) + 1 != expected_len:
        error_msg = f"La longitud del payload del batch no coincide (esperada: {expected_len}, real: {len(payload) + 1})"
        return error_msg
    
    return None # Sin errores

def _extract_bets_from_payload(payload):
    """
    Valida y remueve el footer '|END_BATCH' y extrae las apuestas individuales.
    Devuelve (bets_list, None) si es exitoso, o (None, error_msg) si falla.
    """
    footer = "|END_BATCH"
    if not payload.endswith(footer):
        return None, "El payload del batch no termina con el footer '|END_BATCH'"
    
    # Se extrae el cuerpo del mensaje que contiene las apuestas
    bets_body = payload[:-len(footer)]
    
    # Se separan las apuestas por ':' y se eliminan posibles strings vacíos
    individual_bets = [bet for bet in bets_body.split(':') if bet]

    return individual_bets, None

def decode_batch(batch_message):
    """
    Decodifica y valida un lote completo (batch) orquestando funciones auxiliares.
    """
    try:
        header, payload, error = _split_batch_header_payload(batch_message)
        if error:
            return None, error

        error = _validate_batch_header_and_length(header, payload)
        if error:
            return None, error

        individual_bets, error = _extract_bets_from_payload(payload)
        if error:
            return None, error

        return individual_bets, None

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