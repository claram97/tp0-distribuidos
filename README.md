# TP0: Docker + Comunicaciones + Concurrencia

## Instrucciones de uso
El repositorio cuenta con un **Makefile** que incluye distintos comandos en forma de targets. Los targets se ejecutan mediante la invocación de:  **make \<target\>**. Los target imprescindibles para iniciar y detener el sistema son **docker-compose-up** y **docker-compose-down**, siendo los restantes targets de utilidad para el proceso de depuración.

Los targets disponibles son:

| target  | accion  |
|---|---|
|  `docker-compose-up`  | Inicializa el ambiente de desarrollo. Construye las imágenes del cliente y el servidor, inicializa los recursos a utilizar (volúmenes, redes, etc) e inicia los propios containers. |
| `docker-compose-down`  | Ejecuta `docker-compose stop` para detener los containers asociados al compose y luego  `docker-compose down` para destruir todos los recursos asociados al proyecto que fueron inicializados. Se recomienda ejecutar este comando al finalizar cada ejecución para evitar que el disco de la máquina host se llene de versiones de desarrollo y recursos sin liberar. |
|  `docker-compose-logs` | Permite ver los logs actuales del proyecto. Acompañar con `grep` para lograr ver mensajes de una aplicación específica dentro del compose. |
| `docker-image`  | Construye las imágenes a ser utilizadas tanto en el servidor como en el cliente. Este target es utilizado por **docker-compose-up**, por lo cual se lo puede utilizar para probar nuevos cambios en las imágenes antes de arrancar el proyecto. |
| `build` | Compila la aplicación cliente para ejecución en el _host_ en lugar de en Docker. De este modo la compilación es mucho más veloz, pero requiere contar con todo el entorno de Golang y Python instalados en la máquina _host_. |


## Solución Propuesta

Este README detalla las decisiones de diseño e implementación tomadas para resolver los ejercicios del TP0, enfocándose en los cambios más relevantes introducidos en cada etapa.

### Parte 1: Introducción a Docker

En esta sección se sentaron las bases del entorno de trabajo, interactuando con Docker y Docker Compose para gestionar nuestros servicios.

#### Ejercicio 1: Generación Dinámica del Compose

Para cumplir con la consigna de generar un `docker-compose.yaml` con una cantidad variable de clientes, se optó por un enfoque mixto:

- **`generar_compose.sh`**: Un script de Bash simple que actúa como *wrapper*. Su única responsabilidad es validar que se pasen exactamente dos argumentos (nombre del archivo de salida y cantidad de clientes) y luego invocar al script de Python.
- **`generar_compose.py`**: Este script contiene la lógica principal. Parsea los argumentos, valida que la cantidad de clientes no supere el máximo de 5 (ya que solo hay 5 datasets de agencias) y genera dinámicamente el contenido del archivo YAML. Este enfoque permite manejar la lógica de generación y las validaciones de forma más cómoda y robusta que en Bash puro.

---

#### Ejercicio 2: Configuración Externalizada

Para que los cambios en los archivos de configuración (`config.ini`, `config.yaml`) no requieran reconstruir las imágenes, se utilizaron **volúmenes de Docker**.

Los archivos de configuración locales se montan directamente dentro de los contenedores en las rutas esperadas. De esta forma, el contenedor siempre lee la versión más reciente del archivo que está en el *host*. Para completar la solución, se agregaron las rutas de estos archivos al `.dockerignore` para asegurar que no se copien dentro de la imagen durante el `build`, evitando así cualquier tipo de conflicto.

---

#### Ejercicio 3: Script de Validación con `netcat`

Se creó el script `validar-echo-server.sh` para verificar el comportamiento del servidor sin necesidad de instalar `netcat` en el host ni exponer puertos. La clave fue aprovechar las **redes de Docker**:

1.  El script levanta un contenedor efímero (`--rm`) basado en la imagen ligera `alpine`.
2.  Este contenedor se conecta a la misma red Docker que el servidor (`--network "$NETWORK_NAME"`). Al estar en la misma red, los contenedores pueden comunicarse entre sí usando sus nombres de servicio como si fueran DNS (en este caso, `server`).
3.  Dentro del contenedor, se ejecuta `nc server <puerto>` para enviar un mensaje y se captura la respuesta.
4.  Finalmente, se compara el mensaje enviado con el recibido para determinar si el test fue exitoso (`success`) o no (`fail`).

Este método es ideal porque testea la comunicación en un entorno aislado y controlado, idéntico al que usan los propios clientes del sistema.

---

#### Ejercicio 4: Cierre *Graceful* (SIGTERM)

Para asegurar un cierre ordenado de los servicios, se implementó el manejo de la señal `SIGTERM`. Esto es fundamental al usar `docker-compose down`, que envía esta señal a los contenedores antes de forzar su detención (gracias al flag `-t <timeout>`).

-   **Servidor (Python)**: Se implementó un *signal handler* que, al recibir `SIGTERM`, invoca a una función `stop()`. Esta función se encarga de cerrar el socket principal y todas las conexiones activas de los clientes, que se gestionan en un diccionario. Esto libera todos los recursos de red correctamente.
-   **Cliente (Go)**: La solución fue un poco más "trambólica", como bien dijiste. Se utilizó el manejo de contextos y goroutines de Go. El bucle principal del cliente se ejecuta en una goroutine separada. El *thread* principal, mientras tanto, escucha dos canales: uno que avisa cuando la goroutine de trabajo termina y otro que se activa al recibir una señal del sistema (`os.Signal`, específicamente `SIGTERM`). Usando `select`, el programa reacciona a lo que ocurra primero, garantizando que una señal de terminación interrumpa el flujo y permita un cierre limpio.

---

### Parte 2: Lotería Nacional - Comunicaciones

En esta parte se abandonó el "echo server" para implementar el caso de uso de la Lotería, definiendo un protocolo de comunicación y una lógica de negocio más compleja.

#### Ejercicio 5: Protocolo de Apuestas Individuales

Se diseñó e implementó un protocolo de comunicación para el envío de apuestas. La solución se dividió en varias capas para separar responsabilidades:

1.  **Capa de Dominio**: Se crearon *structs* (Go) y clases (Python) para representar el concepto de una `Bet` (apuesta), conteniendo todos sus datos (nombre, DNI, etc.).
2.  **Capa de Serialización (`communicationUtils`)**: Se crearon funciones `encode_message` y `decode_message` para convertir una `Bet` en un string con un formato definido y viceversa. El formato elegido fue:
    `LEN=<longitud>|KEY1=VALUE1|KEY2=VALUE2|...|END`
    - La `LEN` al inicio es crucial para que el receptor sepa cuántos bytes leer, evitando problemas de *short reads*.
    - El formato `KEY=VALUE` y los separadores `|` lo hacen legible y fácil de parsear.
3.  **Capa de Comunicación (`communication`)**: Esta capa se abstrae del contenido del mensaje. Su única responsabilidad es enviar y recibir bytes de forma confiable, implementando bucles para leer (`read`) y escribir (`write`) hasta asegurarse de que se transfirió toda la cantidad de datos esperada. Esto soluciona los problemas de *short reads/writes*, donde una única llamada a `recv` o `send` podría no leer/enviar el mensaje completo.

En el lado del cliente, las apuestas se leían como variables de entorno a través de un archivo `client.env`, facilitando la prueba con distintos datos.

---

#### Ejercicio 6: Procesamiento por Batches

Para optimizar el envío de múltiples apuestas, se extendió el protocolo para soportar *batches* (lotes).

-   **Cliente (Go)**: Ahora lee las apuestas desde un archivo `.csv` (montado como volumen), las agrupa en lotes de un tamaño configurable (respetando un máximo de 8kB por paquete) y las envía en una sola transacción de red. Se introdujo un mensaje `FIN_BATCH` para indicar el fin del lote.
-   **Servidor (Python)**: Recibe el *batch* completo, lo decodifica y procesa cada apuesta secuencialmente. Solo si **todas** las apuestas del lote son válidas, responde con un `ACK_BATCH`. Si alguna falla, responde con `BATCH_ERROR`.
-   **Mejora del Protocolo**: Un detalle técnico importante surgió al calcular la longitud de los mensajes. `len()` en Python cuenta caracteres, mientras que `len()` en Go cuenta bytes. Dado que los caracteres UTF-8 pueden ocupar más de un byte (ej: tildes, ñ), esto causaba discrepancias. La solución fue usar `utf8.RuneCountInString` en Go para contar caracteres (runas), alineando así el comportamiento de ambos lenguajes y asegurando que el campo `LEN` del protocolo sea consistente.

---

#### Ejercicio 7: Sincronización para el Sorteo

La lógica final requería que el servidor esperara a todos los clientes antes de realizar el sorteo y responder las consultas de ganadores.

-   **Flujo**:
    1.  Cada cliente, al terminar de enviar todos sus *batches*, envía un mensaje `FIN`.
    2.  El servidor recibe las conexiones de todos los clientes y procesa sus apuestas. A medida que recibe los mensajes `FIN`, lleva la cuenta de cuántos clientes han terminado.
    3.  Una vez que el servidor recibe la confirmación del último cliente, considera que el sorteo se ha realizado.
    4.  A partir de ese momento, empieza a responder a cada cliente.
-   **Procesamiento de Ganadores**: Para evitar cargar todo el archivo de apuestas en memoria (lo que sería un problema con millones de apuestas), se optó por una estrategia de *streaming*. Por cada cliente que pide sus ganadores, el servidor **recorre el archivo completo de apuestas en el disco**, y si encuentra una apuesta ganadora que pertenece a esa agencia, la envía en el momento. Si bien esto genera más lecturas de disco (una por cada cliente), garantiza un **uso de memoria mínimo y constante**, sin importar el tamaño del dataset.

---

### Parte 3: Concurrencia

#### Ejercicio 8: Servidor Concurrente

Finalmente, se modificó el servidor para que pudiera atender a múltiples clientes en paralelo.

-   **Modelo de Concurrencia**: Se implementó un modelo de **un thread por cliente**. Al aceptar una nueva conexión, el *thread* principal del servidor deriva el manejo de ese cliente a un *thread* trabajador nuevo y vuelve inmediatamente a esperar más conexiones.
-   **Sincronización**: Dado que ahora múltiples *threads* podían intentar escribir en el archivo de apuestas (`bets.json`) al mismo tiempo, era necesario proteger este recurso compartido.
    -   **Locks**: Se utilizó un `threading.Lock` para asegurar que la escritura en el archivo de apuestas sea una **operación atómica**. Cualquier *thread* que necesite escribir debe adquirir el *lock* primero, y lo libera al terminar. Esto previene *race conditions* y corrupción de datos.
    -   **Barrera**: Para la lógica del sorteo, se usó una `threading.Barrier`. La barrera se inicializa con el número de clientes. Cada *thread*, al recibir el mensaje `FIN` de su cliente, llama a `barrier.wait()`. El *thread* se queda bloqueado en ese punto hasta que el último cliente también llega. Una vez que todos están sincronizados en la barrera, se liberan para empezar la fase de envío de ganadores. Esto asegura de forma elegante y eficiente que ningún cliente reciba ganadores antes de que todos hayan terminado de enviar sus apuestas.

La elección de *multithreading* en Python es adecuada para este caso porque la tarea es **intensiva en I/O** (espera de red, escritura en disco), no en CPU. Por lo tanto, el [Global Interpreter Lock (GIL)](https://wiki.python.org/moin/GlobalInterpreterLock) no representa un cuello de botella, ya que los *threads* liberan el GIL mientras esperan por operaciones de I/O, permitiendo que otros *threads* se ejecuten.