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