package common

import (
	"fmt"
	"strings"
	"strconv"
)

const SuccessStatus = "success"
const FieldsNumber = 4 // LEN, STATUS, INFO, END

func EncodedBet(data BetData, clientID string, msgID int) string {
	dataStr := fmt.Sprintf(
		"NOMBRE=%v|APELLIDO=%v|DOCUMENTO=%v|NACIMIENTO=%v|NUMERO=%v|CLIENT_ID=%v|Message N°=%v|END",
		data.Nombre,
		data.Apellido,
		data.Documento,
		data.Nacimiento,
		data.Numero,
		clientID,
		msgID,
	)
	return fmt.Sprintf("LEN=%d|%s\n", len(dataStr), dataStr)
}

// ParseResponse valida y decodifica una respuesta del servidor.
// Formato esperado: LEN=<n>|STATUS=<status>|INFO=<info>|END
// Devuelve: status, info, error
func CheckResponseStatus(response string) (string, string, error) {
    parts := strings.Split(response, "|")

    if len(parts) < FieldsNumber {
        return "", "", fmt.Errorf("invalid_format: %q", response)
    }

    expectedLen, err := parseLenField(parts[0])
    if err != nil {
        return "", "", fmt.Errorf("invalid_len_field: %w", err)
    }

    // Reconstruimos el cuerpo de la respuesta (STATUS|INFO|END)
    responseBody := strings.Join(parts[1:4], "|")

    if len(responseBody) != expectedLen {
        return "", "", fmt.Errorf("len_mismatch: expected %d, got %d", expectedLen, len(responseBody))
    }

    status, info, err := parseStatusAndInfo(parts[1], parts[2])
    if err != nil {
        return "", "", fmt.Errorf("invalid_status_info: %w", err)
    }

    return status, info, nil
}

// parseStatusAndInfo extrae los valores de STATUS e INFO.
// Ejemplo: "STATUS=success" → "success"
func parseStatusAndInfo(statusField, infoField string) (string, string, error) {
    statusParts := strings.Split(statusField, "=")
    infoParts := strings.Split(infoField, "=")

    // Ambos campos deben ser KEY=VALUE
    if len(statusParts) != 2 || len(infoParts) != 2 {
        return "", "", fmt.Errorf("bad format in status/info fields: %q | %q", statusField, infoField)
    }

    return statusParts[1], infoParts[1], nil
}

// parseLenField valida y devuelve el entero LEN declarado en el mensaje.
// Ejemplo: "LEN=25" → 25
func parseLenField(field string) (int, error) {
    parts := strings.Split(field, "=")
    if len(parts) != 2 {
        return 0, fmt.Errorf("bad format in LEN field: %q", field)
    }

    expectedLen, err := strconv.Atoi(parts[1])
    if err != nil {
        return 0, fmt.Errorf("LEN not an integer: %q", parts[1])
    }
    return expectedLen, nil
}
