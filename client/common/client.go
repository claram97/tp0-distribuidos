package common

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"os"
	"strings"
	"time"
	"unicode/utf8"

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

func (c *Client) StartClientLoop(ctx context.Context, agencyFile *os.File) error {
	conn, err := c.connectWithRetries(3, 2*time.Second)
	if err != nil {
		return fmt.Errorf("connection_error_after_retries: %w", err)
	}
	defer conn.Close()

	reader := bufio.NewReader(conn)
	scanner := bufio.NewScanner(agencyFile)

	if err := c.processBatches(ctx, scanner, conn, reader); err != nil {
		return err
	}

	if err := c.sendFinAndWaitAck(conn, reader); err != nil {
		return err
	}

	log.Infof("action: client_finished_gracefully | result: success | client_id: %v", c.config.ID)
	return nil
}

// connectWithRetries intenta conectarse varias veces antes de fallar
func (c *Client) connectWithRetries(attempts int, delay time.Duration) (net.Conn, error) {
	var conn net.Conn
	var err error
	for i := 1; i <= attempts; i++ {
		conn, err = CreateClientSocket(c.config.ServerAddress, c.config.ID)
		if err == nil {
			return conn, nil
		}
		log.Warningf("action: create_conn | result: retrying | attempt: %d | client_id: %v | error: %v", i, c.config.ID, err)
		time.Sleep(delay)
	}
	log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
	return nil, err
}

// processBatches se encarga de leer líneas, generar mensajes y enviarlos en batches
func (c *Client) processBatches(ctx context.Context, scanner *bufio.Scanner, conn net.Conn, reader *bufio.Reader) error {
	messages := make([]string, 0, 100)
	batchSize := 0
	footer := "|END_BATCH\n"
	msgID := 1

	for scanner.Scan() {
		if ctx.Err() != nil {
			log.Infof("action: exit | result: sigterm | client_id: %v", c.config.ID)
			return fmt.Errorf("context_cancelled")
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
			if err := c.sendBatch(conn, reader, messages, footer); err != nil {
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
		if err := c.sendBatch(conn, reader, messages, footer); err != nil {
			return err
		}
	}

	if err := scanner.Err(); err != nil {
		log.Errorf("action: scanner_error | result: fail | client_id: %v | error: %v", c.config.ID, err)
	}

	return nil
}

// sendBatch envía un batch y espera la respuesta del servidor
func (c *Client) sendBatch(conn net.Conn, reader *bufio.Reader, messages []string, footer string) error {
	batchContent := strings.Join(messages, "") + footer
	batchLen := utf8.RuneCountInString(batchContent)
	batchToSend := fmt.Sprintf("BATCH_LEN=%d|%s", batchLen, batchContent)

	log.Infof("Sending batch (lines %d, characters %d)", len(messages), batchLen)
	if err := SendMessage(conn, batchToSend, c.config.ID); err != nil {
		log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("send_batch_error: %w", err)
	}
	log.Infof("action: batch_sent | result: success | client_id: %v", c.config.ID)

	if _, err := ReadResponse(reader, c.config.ID); err != nil {
		log.Errorf("action: batch_error_received | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("batch_error: %w", err)
	}
	return nil
}

// sendFinAndWaitAck envía FIN, espera ACK del servidor y responde con ACK final
func (c *Client) sendFinAndWaitAck(conn net.Conn, reader *bufio.Reader) error {
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

	if err := SendMessage(conn, "ACK_FIN\n", c.config.ID); err != nil {
		log.Errorf("action: send_client_ack_fin | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("send_client_ack_fin_error: %w", err)
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
