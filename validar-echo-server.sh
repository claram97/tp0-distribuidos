#!/bin/bash

# Pre-condición: la red existe con este nombre.
NETWORK_NAME="tp0_testing_net"
# Servicio al que me conecto.
SERVER_NAME="server"
SERVER_PORT="12345"

MESSAGE="Hello, server!"

# Ejecuto un contenedor que se elimina al finalizar la ejecución.
# El contenedor usa una imágen de alpine y ejecuta netcat con espera de 1s.
# El resultado se guarda en la variable RESPONSE.
RESPONSE=$(sudo docker run --rm --network "$NETWORK_NAME" alpine sh -c "echo '$MESSAGE' | nc -w 1 '$SERVER_NAME' '$SERVER_PORT'")

if [ "$RESPONSE" = "$MESSAGE" ]; then
    echo "action: test_echo_server | result: success"
    exit 0
else
    echo "action: test_echo_server | result: fail"
    exit 1
fi