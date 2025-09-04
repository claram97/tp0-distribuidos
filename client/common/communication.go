package common

import (
	"bufio"
	"net"
    "time"
    "fmt"
)

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

func ConnectWithRetry(attempts int, clientID string, serverAddress string) (net.Conn, error) {
	var conn net.Conn
	var err error
	for i := 1; i <= attempts; i++ {
		conn, err = CreateClientSocket(serverAddress, clientID)
		if err == nil {
			return conn, nil
		}
		log.Warningf("action: create_conn | result: retrying | attempt: %d | client_id: %v | error: %v", i, clientID, err)
		time.Sleep(2 * time.Second)
	}
	log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", clientID, err)
	return nil, fmt.Errorf("connection_error_after_retries: %w", err)
}