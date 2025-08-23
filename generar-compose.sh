#!/bin/bash

if [ $# -ne 2 ]; then
  echo "Uso: $0 <archivo de salida> <cantidad de clientes>"
  exit 1
fi

output_file=$1
clients=$2

# TO-DO: chequear errores
python3 generar-compose.py --output_file $output_file --clients $clients
