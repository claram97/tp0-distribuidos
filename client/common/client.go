package common

import (
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

			message := ParsedMessage(c.config.Data, c.config.ID, msgID)
			if err := SendMessage(c.conn, message, c.config.ID); err != nil {
				c.conn = nil
				return
			}

			response, err := ReceiveMessage(c.conn, c.config.ID)
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
