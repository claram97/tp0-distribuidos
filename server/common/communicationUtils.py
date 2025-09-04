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

def is_valid_len(len_str, message):
    received_len = (
                len(message[1]) + len(message[2]) + len(message[3]) +
                len(message[4]) + len(message[5]) + len(message[6]) +
                len(message[7]) + len(message[8]) + 8
            )
    return int(len_str) == received_len


def decode_message(message):
    splitted_msg = message.split('|')

    try:
        if len(splitted_msg) != 9:
            return "failed", "el mensaje recibido no tiene el formato esperado", None

        try:
            len_str, nombre, apellido, documento, nacimiento, numero, client_id, msg_id, end = parse_message(splitted_msg)
        except (IndexError, ValueError):
            return "failed", "error al parsear los campos del mensaje", None

        try:
            if not is_valid_len(len_str, splitted_msg):
                return "failed", "la longitud del mensaje recibido no es correcta", None
        except ValueError:
            return "failed", "LEN del mensaje no es un entero válido", None

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
    
def encode_message(status, info):
    response_body = f"STATUS={status}|INFO={info}|END\n"
    response = f"LEN={len(response_body)}|{response_body}"

    return response.encode('utf-8')