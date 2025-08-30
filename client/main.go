package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
	"unicode"

	"github.com/op/go-logging"
	"github.com/pkg/errors"
	"github.com/spf13/viper"

	"github.com/7574-sistemas-distribuidos/docker-compose-init/client/common"
)

var log = logging.MustGetLogger("log")

func isAlpha(s string) bool {
	for _, r := range s {
		if !unicode.IsLetter(r) && r != ' ' {
			return false
		}
	}
	return true
}

// InitConfig Function that uses viper library to parse configuration parameters.
// Viper is configured to read variables from both environment variables and the
// config file ./config.yaml. Environment variables takes precedence over parameters
// defined in the configuration file. If some of the variables cannot be parsed,
// an error is returned
func InitConfig() (*viper.Viper, error) {
	v := viper.New()

	// Configure viper to read env variables with the CLI_ prefix
	v.AutomaticEnv()
	v.SetEnvPrefix("cli")
	// Use a replacer to replace env variables underscores with points. This let us
	// use nested configurations in the config file and at the same time define
	// env variables for the nested configurations
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))

	// Add env variables supported
	v.BindEnv("id")
	v.BindEnv("server", "address")
	v.BindEnv("batch", "maxAmount")
	v.BindEnv("loop", "period")
	v.BindEnv("loop", "amount")
	v.BindEnv("log", "level")

	// Try to read configuration from config file. If config file
	// does not exists then ReadInConfig will fail but configuration
	// can be loaded from the environment variables so we shouldn't
	// return an error in that case
	v.SetConfigFile("./config.yaml")
	if err := v.ReadInConfig(); err != nil {
		fmt.Printf("Configuration could not be read from config file. Using env variables instead")
	}

	// Parse time.Duration variables and return an error if those variables cannot be parsed
	if _, err := time.ParseDuration(v.GetString("loop.period")); err != nil {
		return nil, errors.Wrapf(err, "Could not parse CLI_LOOP_PERIOD env var as time.Duration.")
	}

	// Validate that batch max amount is positive
	if v.GetInt("batch.maxAmount") <= 0 {
		return nil, errors.New("CLI_BATCH_MAXAMOUNT env var must be a positive integer.")
	}

	// Validate that loop amount is positive
	if v.GetInt("loop.amount") <= 0 {
		return nil, errors.New("CLI_LOOP_AMOUNT env var must be a positive integer.")
	}

	// Validate that ID is not empty
	if v.GetString("id") == "" {
		return nil, errors.New("CLI_ID env var must be set and non empty.")
	}

	// Validate that server address is not empty
	if v.GetString("server.address") == "" {
		return nil, errors.New("CLI_SERVER_ADDRESS env var must be set and non empty.")
	}

	return v, nil
}

// InitLogger Receives the log level to be set in go-logging as a string. This method
// parses the string and set the level to the logger. If the level string is not
// valid an error is returned
func InitLogger(logLevel string) error {
	baseBackend := logging.NewLogBackend(os.Stdout, "", 0)
	format := logging.MustStringFormatter(
		`%{time:2006-01-02 15:04:05} %{level:.5s}     %{message}`,
	)
	backendFormatter := logging.NewBackendFormatter(baseBackend, format)

	backendLeveled := logging.AddModuleLevel(backendFormatter)
	logLevelCode, err := logging.LogLevel(logLevel)
	if err != nil {
		return err
	}
	backendLeveled.SetLevel(logLevelCode, "")

	// Set the backends to be used.
	logging.SetBackend(backendLeveled)
	return nil
}

// PrintConfig Print all the configuration parameters of the program.
// For debugging purposes only
func PrintConfig(v *viper.Viper) {
	log.Infof(
		"action: config | result: success | client_id: %s | server_address: %s | batch_max_amount : %v | loop_amount: %v | loop_period: %v | log_level: %s",
		v.GetString("id"),
		v.GetString("server.address"),
		v.GetInt("batch.maxAmount"),
		v.GetInt("loop.amount"),
		v.GetDuration("loop.period"),
		v.GetString("log.level"),
	)
}

func getClientConfig(v *viper.Viper) common.ClientConfig {

	return common.ClientConfig{
		ServerAddress:  v.GetString("server.address"),
		ID:             v.GetString("id"),
		LoopAmount:     v.GetInt("loop.amount"),
		LoopPeriod:     v.GetDuration("loop.period"),
		BatchMaxAmount: v.GetInt("batch.maxAmount"),
	}
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM)
	defer stop()

	v, err := InitConfig()
	if err != nil {
		log.Criticalf("%s", err)
		os.Exit(1)
	}

	if err := InitLogger(v.GetString("log.level")); err != nil {
		log.Criticalf("%s", err)
		os.Exit(1)
	}

	PrintConfig(v)

	clientConfig := getClientConfig(v)
	client := common.NewClient(clientConfig)

	fileName := fmt.Sprintf("../data/agency-%s.csv", clientConfig.ID)
	file, err := os.Open(fileName)
	if err != nil {
		log.Errorf("action: file_open | result: fail | client_id: %s | error: %v", clientConfig.ID, err)
		os.Exit(1)
	}

	done := make(chan struct{})
	var clientErr error
	go func() {
		clientErr = client.StartClientLoop(ctx, file)
		close(done)
	}()

	select {
	case <-done:
		if clientErr != nil {
			log.Errorf("action: client_finished | result: fail | client_id: %s | error: %v", clientConfig.ID, clientErr)
			file.Close()
			client.Close()
			if strings.Contains(clientErr.Error(), "batch_error") || strings.Contains(clientErr.Error(), "final_batch_error") {
				os.Exit(2)
			} else if strings.Contains(clientErr.Error(), "connection_error") {
				os.Exit(3)
			} else {
				os.Exit(1)
			}
		}
		log.Infof("action: client_finished | result: success | client_id: %s", clientConfig.ID)
	case <-ctx.Done():
		log.Infof("action: sigterm_received | result: exiting | client_id: %s", clientConfig.ID)
	}

	file.Close()
	client.Close()
}
