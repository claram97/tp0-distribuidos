package common

import (
	"fmt"
	"bufio"
	"strings"
	"unicode/utf8"
)

const Footer = "|END_BATCH\n"
const ClientDataFieldsNumber = 5 // NOMBRE, APELLIDO, DOCUMENTO, NACIMIENTO, NUMERO

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
	return fmt.Sprintf("LEN=%d|%s", utf8.RuneCountInString(dataStr), dataStr)
}

func CheckBatchError(reader *bufio.Reader, clientID string) error {
	response, err := reader.ReadString('\n')
	if err != nil {
		log.Errorf("action: read_response | result: fail | client_id: %v | error: %v", clientID, err)
		return err
	}

	trimmedResponse := strings.TrimSpace(response)
	log.Infof("action: response_received | result: success | client_id: %v | response: %s", clientID, trimmedResponse)
	if trimmedResponse == "BATCH_ERROR" || trimmedResponse == "ERROR_BATCH" {
		return fmt.Errorf("server returned batch error")
	}
	return nil
}