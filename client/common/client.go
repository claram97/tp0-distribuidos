package common

import (
	"bufio"
	"fmt"
	"net"
	"time"
	"context"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

type BetData struct {
	Nombre     string
	Apellido   string
	Documento  string
	Nacimiento string
	Numero     string
}

type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
	Data          BetData
}

type Client struct {
	config ClientConfig
	conn   net.Conn
}

func NewClient(config ClientConfig) *Client {
	return &Client{config: config}
}

func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return err
	}
	c.conn = conn
	return nil
}

//
func parsedMessage(data BetData, clientID string, msgID int) string {
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

func (c *Client) sendMessage(message string) error {
    msgBytes := []byte(message)
    totalWritten := 0
    for totalWritten < len(msgBytes) {
        n, err := c.conn.Write(msgBytes[totalWritten:])
        if err != nil {
            log.Errorf("action: send_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
            c.conn.Close()
            c.conn = nil
            return err
        }
        totalWritten += n
    }
    return nil
}

func (c *Client) receiveMessage() (string, error) {
    msg, err := bufio.NewReader(c.conn).ReadString('\n')
    c.conn.Close()
    c.conn = nil
    if err != nil {
        log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return "", err
    }
    return msg, nil
}

// ---- funciones auxiliares ----

func (c *Client) StartClientLoop(ctx context.Context) {
	for msgID := 1; msgID <= c.config.LoopAmount; msgID++ {
		select {
		case <-ctx.Done():
			log.Infof("action: exit | result: success | client_id: %v", c.config.ID)
			return
		default:
			if err := c.createClientSocket(); err != nil {
				return
			}

			message := parsedMessage(c.config.Data, c.config.ID, msgID)
			if err := c.sendMessage(message); err != nil {
				return
			}

			response, err := c.receiveMessage()
			if err != nil {
				return
			}

			log.Infof("action: apuesta_enviada | result: success | dni: %s | numero: %s",
				c.config.Data.Documento, c.config.Data.Numero)

			status, info, err := ParseResponse(response)
			if err != nil {
				log.Errorf("action: parse_response | result: failed | client_id: %v | error: %v", c.config.ID, err)
			} else if status == "success" {
				log.Infof("action: server_response | result: success | client_id: %v | info: %v", c.config.ID, info)
			} else {
				log.Errorf("action: server_response | result: failed | client_id: %v | info: %v", c.config.ID, info)
			}

			if status == "success" {
				log.Infof("action: server_response | result: success | client_id: %v | info: %v", c.config.ID, info)
			} else {
				log.Errorf("action: server_response | result: failed | client_id: %v | info: %v", c.config.ID, info)
			}


			select {
			case <-ctx.Done():
				log.Infof("action: loop_interrupted | result: sigterm | client_id: %v", c.config.ID)
				return
			case <-time.After(c.config.LoopPeriod):
			}
		}
	}

	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		log.Info("action: client_conn_closed | result: success")
		c.conn = nil
	}
}
