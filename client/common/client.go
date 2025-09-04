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

const betsSeparator = ":"

func NewClient(config ClientConfig) *Client {
	return &Client{config: config}
}


// buildBatch construye el contenido de un batch y devuelve el string listo para enviar.
func buildBatch(messages []string, footer string) string {
	batchContent := strings.Join(messages, "") + footer
	batchLen := utf8.RuneCountInString(batchContent)
	return fmt.Sprintf("BATCH_LEN=%d|%s", batchLen, batchContent)
}

// sendBatch envía un batch y espera la respuesta del servidor.
func sendBatch(conn net.Conn, reader *bufio.Reader, batch string, clientID string, isFinal bool) error {
	action := "batch_sent"
	if isFinal {
		action = "final_batch_sent"
	}

	if err := SendMessage(conn, batch, clientID); err != nil {
		log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", clientID, err)
		return fmt.Errorf("send_batch_error: %w", err)
	}
	log.Infof("action: %s | result: success | client_id: %v", action, clientID)

	if err := ReadResponse(reader, clientID); err != nil {
		log.Errorf("action: batch_ack | result: fail | client_id: %v | error: %v", clientID, err)
		return fmt.Errorf("batch_error: %w", err)
	}
	return nil
}

func ReadResponse(reader *bufio.Reader, clientID string) error {
	response, err := reader.ReadString('\n')
	if err != nil {
		log.Errorf("action: read_response | result: fail | client_id: %v | error: %v", clientID, err)
		return err
	}

	trimmedResponse := strings.TrimSpace(response)
	log.Infof("action: response_received | result: success | client_id: %v | response: %s", clientID, trimmedResponse)
	if trimmedResponse == "BATCH_ERROR" || trimmedResponse == "ERROR_BATCH" {
		return fmt.Errorf("server returned batch error")
	}
	return nil
}

func (c *Client) StartClientLoop(ctx context.Context, agencyFile *os.File) error {
	conn, err := ConnectWithRetry(3, c.config.ID, c.config.ServerAddress)
	if err != nil {
		log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("connection_error_after_retries: %w", err)
	}
	defer conn.Close()

	if err != nil {
		log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("connection_error_after_retries: %w", err)
	}
	defer conn.Close()

	reader := bufio.NewReader(conn)
	scanner := bufio.NewScanner(agencyFile)

	messages := make([]string, 0, 100)
	batchSize := 0
	footer := Footer
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
		if len(data) != ClientDataFieldsNumber {
			log.Errorf("action: parse_line | result: fail | line: %s", line)
			continue
		}

		betData := BetData{
			Nombre: data[0], Apellido: data[1], Documento: data[2],
			Nacimiento: data[3], Numero: data[4],
		}
		msg := EncodedBet(betData, c.config.ID, msgID) + betsSeparator
		msgBytes := len([]byte(msg))
		tentativeSize := batchSize + msgBytes + len([]byte(footer))

		// Flush si llegamos a los límites
		if tentativeSize >= 8192 || len(messages) == c.config.BatchMaxAmount {
			batch := buildBatch(messages, footer)
			if err := sendBatch(conn, reader, batch, c.config.ID, false); err != nil {
				return err
			}
			messages = messages[:0]
			batchSize = 0
		}

		messages = append(messages, msg)
		batchSize += msgBytes
		msgID++
	}

	// Enviar batch final si queda algo
	if len(messages) > 0 {
		batch := buildBatch(messages, footer)
		if err := sendBatch(conn, reader, batch, c.config.ID, true); err != nil {
			return err
		}
	}

	if err := scanner.Err(); err != nil {
		log.Errorf("action: scanner_error | result: fail | client_id: %v | error: %v", c.config.ID, err)
	}

	if err := SendMessage(conn, "FIN\n", c.config.ID); err != nil {
		return fmt.Errorf("send_fin_error: %w", err)
	}
	if err := ReadResponse(reader, c.config.ID); err != nil {
		return fmt.Errorf("fin_response_error: %w", err)
	}

	log.Infof("action: all_batches_sent_and_acked | result: success | client_id: %v", c.config.ID)
	return nil
}

func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		log.Info("action: client_conn_closed | result: success")
		c.conn = nil
	}
}
