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

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
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

func (c *Client) StartClientLoop(ctx context.Context) {
    for msgID := 1; msgID <= c.config.LoopAmount; msgID++ {
        if c.shouldStop(ctx) {
            return
        }

        if err := c.createClientSocket(); err != nil || c.conn == nil {
            log.Errorf("action: connect | result: fail | client_id: %v", c.config.ID)
            return
        }

        if err := c.sendClientMessage(msgID); err != nil {
            log.Errorf("action: send_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
            c.conn.Close()
            return
        }

        msg, err := c.receiveServerMessage()
        c.conn.Close()
        if err != nil {
            log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
            return
        }

        log.Infof("action: receive_message | result: success | client_id: %v | msg: %v", c.config.ID, msg)

        if c.shouldStopDuringSleep(ctx) {
            return
        }
    }

    log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

func (c *Client) shouldStop(ctx context.Context) bool {
    select {
    case <-ctx.Done():
        log.Infof("action: loop_interrupted | result: sigterm_received | client_id: %v", c.config.ID)
        return true
    default:
        return false
    }
}

func (c *Client) shouldStopDuringSleep(ctx context.Context) bool {
    select {
    case <-ctx.Done():
        log.Infof("action: loop_interrupted_during_sleep | result: sigterm_received | client_id: %v", c.config.ID)
        return true
    case <-time.After(c.config.LoopPeriod):
        return false
    }
}

func (c *Client) sendClientMessage(msgID int) error {
    message := fmt.Sprintf("[CLIENT %v] Message N°%v\n", c.config.ID, msgID)
    _, err := fmt.Fprintf(c.conn, message)
    return err
}

func (c *Client) receiveServerMessage() (string, error) {
    return bufio.NewReader(c.conn).ReadString('\n')
}

func (c *Client) Close() {
    if c.conn != nil {
        c.conn.Close()
        log.Info("action: client_conn_closed | result: success")
    }
}
