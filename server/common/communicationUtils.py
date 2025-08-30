def parse_message(splitted_msg):
    # Esta función asume que splitted_msg tiene 9 elementos
    # Si hay error, lanza la excepción
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

        # --- LÓGICA CORREGIDA PARA CARACTERES ---
        # Se quita .encode('utf-8') para contar caracteres en lugar de bytes.
        if len(payload) != expected_len:
            return "failed", f"la longitud del payload no coincide (esperada: {expected_len}, real: {len(payload)})", None

        # Se verifica que el último campo sea el marcador 'END'
        splitted_payload = payload.split('|')
        if not splitted_payload or splitted_payload[-1] != 'END':
            return "failed", "el payload no termina con el marcador 'END'", None

        # Se quita el marcador 'END' para procesar solo los campos KEY=VALUE
        fields_to_process = splitted_payload[:-1]

        if len(fields_to_process) != 7:
            return "failed", f"el payload no tiene los 7 campos KEY=VALUE esperados", None

        data = {}
        for field in fields_to_process:
            key_value = field.split('=', 1)
            if len(key_value) != 2:
                # El campo 'END' ya fue filtrado, así que esto solo fallaría por un campo malformado
                return "failed", f"el campo '{field}' no tiene el formato KEY=VALUE", None
            key, value = key_value
            data[key.strip()] = value.strip()

        # 4. Realizar validaciones específicas de los datos
        documento = data.get("DOCUMENTO")
        if not documento or len(documento) != 8 or not documento.isdigit():
            return "failed", "el documento debe tener 8 dígitos", None
        
        return "success", "none", data

    except Exception as e:
        # Captura general para cualquier otro error inesperado
        return "failed", f"error inesperado al procesar el mensaje: {e}", None
    
def encode_message(status, info):
    response_body = f"STATUS={status}|INFO={info}|END\n"
    # El LEN de la respuesta puede seguir siendo en bytes, no afecta al cliente.
    response = f"LEN={len(response_body)}|{response_body}"

    return response.encode('utf-8')

# Las funciones parse_message y is_valid_len ya no son utilizadas por la lógica principal
# pero se dejan por si son necesarias en otra parte.

def parse_message(splitted_msg):
    # Esta función asume que splitted_msg tiene 9 elementos
    # Si hay error, lanza la excepción
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

def is_valid_len(len_str, message):
    received_len = (
                len(message[1]) + len(message[2]) + len(message[3]) +
                len(message[4]) + len(message[5]) + len(message[6]) +
                len(message[7]) + len(message[8]) + 8
            )
    return int(len_str) == received_len