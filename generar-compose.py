import argparse
import yaml

MAX_CLIENTS = 5

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
                ],
                "volumes": [
                    "./server/config.ini:/server/config.ini:ro"
                ],
                "networks": ["testing_net"]
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

    for i in range(1, clients + 1):
        client_name = f"client{i}"
        data["services"][client_name] = {
            "container_name": client_name,
            "image": "client:latest",
            "entrypoint": "/client",
            "environment": [
                f"CLI_ID={i}",
            ],
            "volumes": [
                "./client/config.yaml:/config.yaml:ro",
                "./.data:/data:rw"
            ],
            "networks": ["testing_net"],
            "depends_on": ["server"]
        }

    with open(file_name, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

def is_valid_client_count(value):
    ivalue = int(value)
    if ivalue < 1 or ivalue > MAX_CLIENTS:
        raise argparse.ArgumentTypeError(f"Invalid number of clients: {value}. Must be between 1 and {MAX_CLIENTS}.")
    return ivalue

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generador de docker-compose")
    parser.add_argument(
        "--output_file", required=True, help="Nombre del archivo de salida"
    )
    parser.add_argument(
        "--clients",
        required=True,
        type=is_valid_client_count,
        help=f"Cantidad de clientes (entre 1 y {MAX_CLIENTS})"
    )

    args = parser.parse_args()
    return args.output_file, args.clients

def main():
    output_file, clients = parse_arguments()
    write_file(output_file, clients)

if __name__ == "__main__":
    main()