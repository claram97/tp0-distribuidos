package common

import (
	"bufio"
	"net"
    "strings"
    "fmt"
)

func ReadResponse(reader *bufio.Reader, clientID string) (string, error) {
	response, err := reader.ReadString('\n')
	if err != nil {
		log.Errorf("action: read_response | result: fail | client_id: %v | error: %v", clientID, err)
		return "", err
	}

	trimmedResponse := strings.TrimSpace(response)

	if trimmedResponse == "BATCH_ERROR" || trimmedResponse == "ERROR_BATCH" {
		return trimmedResponse, fmt.Errorf("server returned batch error")
	}

	return trimmedResponse, nil
}

func SendMessage(conn net.Conn, message string, clientID string) error {
    msgBytes := []byte(message)
    totalWritten := 0
    for totalWritten < len(msgBytes) {
        n, err := conn.Write(msgBytes[totalWritten:])
        if err != nil {
            log.Errorf("action: send_message | result: fail | client_id: %v | error: %v", clientID, err)
            conn.Close()
            return err
        }
        totalWritten += n
    }
    return nil
}

func ReceiveMessage(conn net.Conn, clientID string) (string, error) {
    msg, err := bufio.NewReader(conn).ReadString('\n')
    conn.Close()
    conn = nil
    if err != nil {
        log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v", clientID, err)
        return "", err
    }
    return msg, nil
}

func CreateClientSocket(serverAddress string, clientID string) (net.Conn, error) {
    conn, err := net.Dial("tcp", serverAddress)
    if err != nil {
        log.Criticalf(
            "action: connect | result: fail | client_id: %v | error: %v",
            clientID,
            err,
        )
        return nil, err
    }
    return conn, nil
}
