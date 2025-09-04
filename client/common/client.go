package common

import (
	"net"
	"time"
	"context"
	"fmt"

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

func (c *Client) shouldStop(ctx context.Context) bool {
    select {
    case <-ctx.Done():
        log.Infof("action: exit | result: success | client_id: %v", c.config.ID)
        return true
    default:
        return false
    }
}

func (c *Client) SendBet(ctx context.Context) {
    msgID := 1
    if c.shouldStop(ctx) {
        return
    }

    var conn net.Conn
	var err error	
	for i := 1; i <= 3; i++ {
		conn, err = CreateClientSocket(c.config.ServerAddress, c.config.ID)
		if err == nil {
			break
		}
		log.Warningf("action: create_conn | result: retrying | attempt: %d | client_id: %v | error: %v", i, c.config.ID, err)
		time.Sleep(2 * time.Second)
	}

	if err != nil {
		log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
		c.conn = nil
        return
	}
	defer conn.Close()
    c.conn = conn

    if err := c.handleMessage(msgID); err != nil {
        log.Errorf("action: client_loop | result: fail | client_id: %v | error: %v", c.config.ID, err)
        c.conn = nil
        return
    }

    log.Infof("action: message_sent | result: success | client_id: %v", c.config.ID)
}

func (c *Client) handleMessage(msgID int) error {
    message := ParsedMessage(c.config.Data, c.config.ID, msgID)
    if err := SendMessage(c.conn, message, c.config.ID); err != nil {
        return fmt.Errorf("send_message: %w", err)
    }

    response, err := ReceiveMessage(c.conn, c.config.ID)
    if err != nil {
        return fmt.Errorf("receive_message: %w", err)
    }

    log.Infof("action: apuesta_enviada | result: success | dni: %s | numero: %s",
        c.config.Data.Documento, c.config.Data.Numero)

    status, info, err := ParseResponse(response)
    if err != nil {
        log.Errorf("action: parse_response | result: failed | client_id: %v | error: %v", c.config.ID, err)
        return err
    }

    if status == "success" {
        log.Infof("action: server_response | result: success | client_id: %v | info: %v", c.config.ID, info)
    } else {
        log.Errorf("action: server_response | result: failed | client_id: %v | info: %v", c.config.ID, info)
    }
    return nil
}

func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		log.Info("action: client_conn_closed | result: success")
		c.conn = nil
	}
}
