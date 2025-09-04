package main

import (
	"fmt"
	"os"
	"strings"
	"time"
	"os/signal"
	"syscall"
	"context"
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

func validateParameters(v *viper.Viper) error {
	nombre := v.GetString("nombre")
	apellido := v.GetString("apellido")
	documento := v.GetString("documento")
	nacimiento := v.GetString("nacimiento")
	numero := v.GetString("numero")

	if nombre == "" || apellido == "" || documento == "" || nacimiento == "" || numero == "" {
		return fmt.Errorf("missing_parameters")
	}

	if !isAlpha(nombre) {
		return fmt.Errorf("nombre must be alphabetic")
	}

	if !isAlpha(apellido) {
		return fmt.Errorf("apellido must be alphabetic")
	}

	if len(documento) != 8 {
		return fmt.Errorf("documento must be 8 digits")
	}

	return nil
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
	v.BindEnv("loop", "period")
	v.BindEnv("loop", "amount")
	v.BindEnv("log", "level")
	v.BindEnv("nombre")
	v.BindEnv("apellido")
	v.BindEnv("documento")
	v.BindEnv("nacimiento")
	v.BindEnv("numero")

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

	// If any of the variables for the bet is not present, we must fail
	requiredVars := []string{"nombre", "apellido", "documento", "nacimiento", "numero"}
	for _, key := range requiredVars {
		if v.GetString(key) == "" {
			return nil, fmt.Errorf("Missing required env var: CLI_%s", strings.ToUpper(key))
		}
	}

	// TO-DO: add validation for correct values (for example, 'documento' has 8 numbers)
	resultOfValidation := validateParameters(v)
	if resultOfValidation != nil {
		return nil, resultOfValidation
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
        "action: config | result: success | client_id: %s | server_address: %s | loop_amount: %v | loop_period: %v | log_level: %s | nombre: %s | apellido: %s | documento: %s | nacimiento: %s | numero: %s",
        v.GetString("id"),
        v.GetString("server.address"),
        v.GetInt("loop.amount"),
        v.GetDuration("loop.period"),
        v.GetString("log.level"),
        v.GetString("nombre"),
        v.GetString("apellido"),
        v.GetString("documento"),
        v.GetString("nacimiento"),
        v.GetString("numero"),
    )
}

func initClient() *common.Client {
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

	betData := common.BetData{
		Nombre:     v.GetString("nombre"),
		Apellido:   v.GetString("apellido"),
		Documento:  v.GetString("documento"),
		Nacimiento: v.GetString("nacimiento"),
		Numero:     v.GetString("numero"),
	}

	clientConfig := common.ClientConfig{
		ServerAddress: v.GetString("server.address"),
		ID:            v.GetString("id"),
		LoopAmount:    v.GetInt("loop.amount"),
		LoopPeriod:    v.GetDuration("loop.period"),
		Data:          betData,
	}

    return common.NewClient(clientConfig)
}

func runClient(ctx context.Context, client *common.Client) {
    client.SendMessage(ctx)
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM)
	defer stop()

	client:= initClient()
	defer client.Close()

	done := make(chan struct{})
	go func() {
		runClient(ctx, client)
		close(done)
	}()

	select {
	case <-done:
		log.Infof("action: exit | result: success")
		os.Exit(0)
	case <-ctx.Done():
		log.Infof("action: exit | result: success")
		os.Exit(0)
	}
}