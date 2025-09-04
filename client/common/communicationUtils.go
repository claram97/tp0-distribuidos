package common

import (
	"bufio"
	"net"
	"fmt"
	"strconv"
	"strings"
	"unicode/utf8"
)

func ParsedMessage(data BetData, clientID string, msgID int) string {
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
	return fmt.Sprintf("LEN=%d|%s", utf8.RuneCountInString(dataStr), dataStr)
}

func ParseResponse(response string) (string, string, error) {
	parts := strings.Split(response, "|")
	if len(parts) < 4 {
		return "", "", fmt.Errorf("invalid_format: %q", response)
	}

	expectedLen, err := parseLenField(parts[0])
	if err != nil {
		return "", "", fmt.Errorf("invalid_len_field: %w", err)
	}

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

func parseStatusAndInfo(statusField, infoField string) (string, string, error) {
	statusParts := strings.Split(statusField, "=")
	infoParts := strings.Split(infoField, "=")

	if len(statusParts) != 2 || len(infoParts) != 2 {
		return "", "", fmt.Errorf("bad format in status/info fields: %q | %q", statusField, infoField)
	}

	return statusParts[1], infoParts[1], nil
}

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

func SendBatch(conn net.Conn, reader *bufio.Reader, messages []string, footer string, clientID string) error {
	batchContent := strings.Join(messages, "") + footer
	batchLen := utf8.RuneCountInString(batchContent)
	batchToSend := fmt.Sprintf("BATCH_LEN=%d|%s", batchLen, batchContent)

	log.Infof("Sending batch (lines %d, characters %d)", len(messages), batchLen)

	if err := SendMessage(conn, batchToSend, clientID); err != nil {
		log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", clientID, err)
		return fmt.Errorf("send_batch_error: %w", err)
	}

	log.Infof("action: batch_sent | result: success | client_id: %v", clientID)

	if _, err := ReadResponse(reader, clientID); err != nil {
		log.Errorf("action: batch_error_received | result: fail | client_id: %v | error: %v", clientID, err)
		return fmt.Errorf("batch_error: %w", err)
	}

	return nil
}