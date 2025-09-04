package common

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"os"
	"strings"
	"time"

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
	ID             string
	ServerAddress  string
	LoopAmount     int
	LoopPeriod     time.Duration
	BatchMaxAmount int
}

type Client struct {
	config ClientConfig
	conn   net.Conn
}

func NewClient(config ClientConfig) *Client {
	return &Client{config: config}
}

func (c *Client) StartClientLoop(ctx context.Context, agencyFile *os.File) error {
	conn, err := ConnectWithRetry(3, c.config.ID, c.config.ServerAddress)
	if err != nil {
		log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("connection_error_after_retries: %w", err)
	}
	defer conn.Close()

	reader := bufio.NewReader(conn)
	scanner := bufio.NewScanner(agencyFile)

	messages := make([]string, 0, 100)
	batchSize := 0
	footer := "|END_BATCH\n"
	msgID := 1

	for scanner.Scan() {
		select {
		case <-ctx.Done():
			log.Infof("action: exit | result: sigterm | client_id: %v", c.config.ID)
			return fmt.Errorf("context_cancelled")
		default:
		}

		line := scanner.Text()
		data := strings.Split(line, ",")
		if len(data) != 5 {
			log.Errorf("action: parse_line | result: fail | line: %s", line)
			continue
		}

		betData := BetData{
			Nombre: data[0], Apellido: data[1], Documento: data[2],
			Nacimiento: data[3], Numero: data[4],
		}
		msg := ParsedMessage(betData, c.config.ID, msgID) + ":"
		msgBytes := len([]byte(msg))
		tentativeSize := batchSize + msgBytes + len([]byte(footer))

		if tentativeSize >= 8192 || len(messages) == c.config.BatchMaxAmount {
			if err := SendBatch(conn, reader, messages, footer, c.config.ID); err != nil {
				return err
			}

			messages = messages[:0]
			batchSize = 0
		}

		messages = append(messages, msg)
		batchSize += msgBytes
		msgID++
	}

	if len(messages) > 0 {
		if err := SendBatch(conn, reader, messages, footer, c.config.ID); err != nil {
			return err
		}
	}

	if err := scanner.Err(); err != nil {
		log.Errorf("action: scanner_error | result: fail | client_id: %v | error: %v", c.config.ID, err)
	}

	log.Infof("action: sending_fin | result: in_progress | client_id: %v", c.config.ID)
	if err := SendMessage(conn, "FIN\n", c.config.ID); err != nil {
		log.Errorf("action: send_fin | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("send_fin_error: %w", err)
	}

	log.Infof("action: waiting_for_winners_and_fin | result: in_progress | client_id: %v", c.config.ID)

	winnerCount := 0

	for {
		msg, err := ReadResponse(reader, c.config.ID)
		if err != nil {
			log.Errorf("action: read_server_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
			return fmt.Errorf("error reading from server: %w", err)
		}

		if msg == "ACK_FIN" {
			log.Infof("action: server_fin_ack_received | result: success | client_id: %v", c.config.ID)
			break
		}

		winnerCount++
	}

	log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %d", winnerCount)

	// Ahora que recibimos el ACK_FIN del servidor, le respondemos con el nuestro.
	log.Infof("action: sending_client_ack_fin | result: in_progress | client_id: %v", c.config.ID)
	if err := SendMessage(conn, "ACK_FIN\n", c.config.ID); err != nil {
		log.Errorf("action: send_client_ack_fin | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("send_client_ack_fin_error: %w", err)
	}

	log.Infof("action: client_finished_gracefully | result: success | client_id: %v", c.config.ID)
	return nil
}

func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		log.Info("action: client_conn_closed | result: success")
		c.conn = nil
	}
}
