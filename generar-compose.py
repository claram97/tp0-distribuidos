import argparse
import yaml

# TO-DO: agregar manejo de errores
def write_file(file_name, clients):
    data = {
        "name": "tp0",
        "services": {
            "server": {
                "container_name": "server",
                "image": "server:latest",
                "entrypoint": "python3 /main.py",
                "environment": [
                    "PYTHONUNBUFFERED=1",
                    "LOGGING_LEVEL=DEBUG"
                ],
                "networks": ["testing_net"]
            },
            "client1": {
                "container_name": "client1",
                "image": "client:latest",
                "entrypoint": "/client",
                "environment": [
                    "CLI_ID=1",
                    "CLI_LOG_LEVEL=DEBUG"
                ],
                "networks": ["testing_net"],
                "depends_on": ["server"]
            }
        },
        "networks": {
            "testing_net": {
                "ipam": {
                    "driver": "default",
                    "config": [
                        {"subnet": "172.25.125.0/24"}
                    ]
                }
            }
        }
    }

    with open(file_name, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

# TO-DO: agregar validaciones de máximos y mínimos
def parse_arguments():
    parser = argparse.ArgumentParser(description="Generador de docker-compose")
    
    parser.add_argument("--output_file", required=True, help="Nombre del archivo de salida que se va a generar")
    parser.add_argument("--clients", required=True, type=int, help="Cantidad de clientes que se van a generar")

    args = parser.parse_args()

    return args.output_file, args.clients


def main():
    output_file, clients = parse_arguments()
    write_file(output_file, clients)

if __name__ == "__main__":
    main()