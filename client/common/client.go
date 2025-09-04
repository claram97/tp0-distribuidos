package common

import (
	"bufio"
	"fmt"
	"net"
	"time"

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

func (c *Client) connectWithRetry(attempts int) error {
    var err error
    for i := 1; i <= attempts; i++ {
        err = c.createClientSocket()
        if err == nil {
            return nil
        }
        log.Warningf("action: create_conn | result: retrying | attempt: %d | client_id: %v | error: %v", i, c.config.ID, err)
        time.Sleep(2 * time.Second)
    }
    log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
    return fmt.Errorf("connection_error_after_retries: %w", err)
}

func (c *Client) sendClientMessage(msgID int) error {
    message := fmt.Sprintf("[CLIENT %v] Message N°%v\n", c.config.ID, msgID)
    _, err := fmt.Fprintf(c.conn, message)
    return err
}

func (c *Client) receiveServerMessage() (string, error) {
    return bufio.NewReader(c.conn).ReadString('\n')
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	// There is an autoincremental msgID to identify every message sent
	// Messages if the message amount threshold has not been surpassed
	for msgID := 1; msgID <= c.config.LoopAmount; msgID++ {
    	err := c.connectWithRetry(3)
		if err != nil {
			log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
			return
		}
		defer c.conn.Close()

		// TODO: Modify the send to avoid short-write
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

		if err != nil {
			log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
				c.config.ID,
				err,
			)
			return
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