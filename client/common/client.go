package common

import (
	"bufio"
	"fmt"
	"net"
	"time"
	"strings"
	"io"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// Bet data to be send to the server
type BetData struct {
    Nombre     string
    Apellido   string
    Documento  string
    Nacimiento string
    Numero     string
}

// ClientConfig Configuration used by the client
type ClientConfig struct {
    ID            string
    ServerAddress string
    LoopAmount    int
    LoopPeriod    time.Duration
    Data         BetData
}

// Client Entity that encapsulates how
type Client struct {
	config ClientConfig
	conn   net.Conn
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config: config,
	}
	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
	}
	c.conn = conn
	return nil
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	// There is an autoincremental msgID to identify every message sent
	// Messages if the message amount threshold has not been surpassed
	for msgID := 1; msgID <= c.config.LoopAmount; msgID++ {
		// Create the connection the server in every loop iteration. Send an
		c.createClientSocket()

		dataStr := fmt.Sprintf(
			"NOMBRE=%v|APELLIDO=%v|DOCUMENTO=%v|NACIMIENTO=%v|NUMERO=%v|CLIENT_ID=%v|Message N°=%v|END",
			c.config.Data.Nombre,
			c.config.Data.Apellido,
			c.config.Data.Documento,
			c.config.Data.Nacimiento,
			c.config.Data.Numero,
			c.config.ID,
			msgID,
		)
		lenStr := len(dataStr)
		finalMsg := fmt.Sprintf("LEN=%d|%s\n", lenStr, dataStr)

		n, err := io.WriteString(c.conn, finalMsg)
		if err != nil {
			log.Errorf("action: send_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
			return
		}
		if n != len(finalMsg) {
			log.Errorf("action: send_message | result: short_write | client_id: %v | written: %d | expected: %d", c.config.ID, n, len(finalMsg))
			return
		}

		log.Infof("Mensaje enviado: %s", finalMsg)

		msg, err := bufio.NewReader(c.conn).ReadString('\n')
		c.conn.Close()

		if err != nil {
			log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

		// Parsear la respuesta del servidor (TO-DO: meterlo en una función)
		parts := strings.Split(msg, "|")
		if len(parts) >= 4 {
			lenField := strings.Split(parts[0], "=")
			if len(lenField) != 2 {
				log.Errorf("action: server_response | result: invalid_len_field | client_id: %v | msg: %v", c.config.ID, msg)
				return
			}
			expectedLen := lenField[1]
			responseBody := strings.Join(parts[1:4], "|")
			if fmt.Sprintf("%d", len(responseBody)) != expectedLen {
				log.Errorf("action: server_response | result: len_mismatch | client_id: %v | expected: %v | got: %v", c.config.ID, expectedLen, len(responseBody))
				return
			}

			status := strings.Split(parts[1], "=")[1]
			info := strings.Split(parts[2], "=")[1]

			if status == "success" {
				log.Infof("action: server_response | result: success | client_id: %v | info: %v", c.config.ID, info)
			} else {
				log.Errorf("action: server_response | result: failed | client_id: %v | info: %v", c.config.ID, info)
			}
		} else {
			log.Errorf("action: server_response | result: invalid_format | client_id: %v | msg: %v", c.config.ID, msg)
		}

		log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
			c.config.ID,
			msg,
		)

		// Wait a time between sending one message and the next one
		time.Sleep(c.config.LoopPeriod)

	}
	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

func (c *Client) Close() {
    if c.conn != nil {
        c.conn.Close()
        log.Info("action: client_conn_closed | result: success")
    }
}
