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
	conn, err := CreateClientSocket(c.config.ServerAddress, c.config.ID)
	if err != nil {
		log.Errorf("action: create_conn | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return fmt.Errorf("connection_error: %w", err)
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
			batchContent := strings.Join(messages, "")
			batchContent = batchContent + footer
			batchLen := utf8.RuneCountInString(batchContent)
			batchToSend := fmt.Sprintf("BATCH_LEN=%d|%s", batchLen, batchContent)

			log.Infof("Sending batch (lines %d, characters %d)", len(messages), batchLen)
			if err := SendMessage(conn, batchToSend, c.config.ID); err != nil {
				log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", c.config.ID, err)
				return fmt.Errorf("send_batch_error: %w", err)
			}
			log.Infof("action: batch_sent | result: success | client_id: %v", c.config.ID)

			if err := ReadResponse(reader, c.config.ID); err != nil {
				log.Errorf("action: batch_error_received | result: fail | client_id: %v | error: %v", c.config.ID, err)
				return fmt.Errorf("batch_error: %w", err)
			}

			messages = messages[:0]
			batchSize = 0
		}

		messages = append(messages, msg)
		batchSize += msgBytes
		msgID++
	}

	if len(messages) > 0 {
		batchContent := strings.Join(messages, "")
		batchContent = batchContent + footer
		batchLen := utf8.RuneCountInString(batchContent)
		batchToSend := fmt.Sprintf("BATCH_LEN=%d|%s", batchLen, batchContent)

		log.Infof("Sending final batch (lines %d, characters %d)", len(messages), batchLen)
		if err := SendMessage(conn, batchToSend, c.config.ID); err != nil {
			log.Errorf("action: send_final_batch | result: fail | client_id: %v | error: %v", c.config.ID, err)
			return fmt.Errorf("send_final_batch_error: %w", err)
		}
		log.Infof("action: final_batch_sent | result: success | client_id: %v", c.config.ID)
		if err := ReadResponse(reader, c.config.ID); err != nil {
			log.Errorf("action: batch_error_received | result: fail | client_id: %v | error: %v", c.config.ID, err)
			return fmt.Errorf("final_batch_error: %w", err)
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

	if err := ReadResponse(reader, c.config.ID); err != nil {
		return fmt.Errorf("fin_response_error: %w", err)
	}

	log.Infof("action: all_batches_sent_and_acked | result: success | client_id: %v", c.config.ID)
	return nil
}

// func (c *Client) handleMessage(msgID int) error {
// 	message := ParsedMessage(c.config.Data, c.config.ID, msgID)
// 	if err := SendMessage(c.conn, message, c.config.ID); err != nil {
// 		return fmt.Errorf("send_message: %w", err)
// 	}

// 	response, err := ReceiveMessage(c.conn, c.config.ID)
// 	if err != nil {
// 		return fmt.Errorf("receive_message: %w", err)
// 	}

// 	log.Infof("action: apuesta_enviada | result: success | dni: %s | numero: %s",
// 		c.config.Data.Documento, c.config.Data.Numero)

// 	status, info, err := ParseResponse(response)
// 	if err != nil {
// 		log.Errorf("action: parse_response | result: failed | client_id: %v | error: %v", c.config.ID, err)
// 		return err
// 	}

// 	if status == "success" {
// 		log.Infof("action: server_response | result: success | client_id: %v | info: %v", c.config.ID, info)
// 	} else {
// 		log.Errorf("action: server_response | result: failed | client_id: %v | info: %v", c.config.ID, info)
// 	}
// 	return nil
// }

func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		log.Info("action: client_conn_closed | result: success")
		c.conn = nil
	}
}
