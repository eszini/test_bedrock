# Guía de usuario: secrets en WSL para Python, C, C++ y Bash

Esta guía describe el mecanismo que ya usa este workspace y establece cómo integrar otros programas sin guardar credenciales en claro dentro del repositorio. Está escrita también como referencia para futuras tareas de desarrollo: se puede pedir que se adapte un programa a estas reglas siguiendo la plantilla de la sección [Instrucción reutilizable para integrar un programa](#instrucción-reutilizable-para-integrar-un-programa).

## 1. Resumen de la solución

El workspace usa **SOPS** para cifrar el archivo de variables y **Age** como mecanismo de cifrado de clave pública:

- `secrets.enc.env` contiene los valores cifrados. Es el archivo que puede versionarse en Git.
- La clave pública Age (el destinatario `age1...`) se usa para cifrar. No permite descifrar y puede compartirse con quien tenga que preparar o actualizar el archivo cifrado.
- La clave privada Age se conserva localmente en WSL, fuera del repositorio, por defecto en `~/.config/sops/age/keys.txt`. SOPS la necesita para descifrar. No se debe subir, copiar al workspace ni incluir en una imagen/artefacto.
- `sops exec-env` descifra el archivo para la ejecución e inyecta las variables de entorno al comando hijo. El programa las lee usando la interfaz normal de su lenguaje: entorno del proceso en Python, `getenv()` en C, `std::getenv()` en C++ o expansión de variables en Bash.

El repositorio contiene un ejemplo de este patrón en `01_simple.sh`, `02_script.sh`, `03_app.py`, `04_app.c`, `05_app.cpp` y `test_01.sh`.

## 2. Qué protege y qué no

El archivo cifrado protege los **valores secretos en reposo** dentro del repositorio. Git puede almacenar el ciphertext y el historial de sus cambios sin almacenar directamente los valores descifrados. Los nombres de variables y cierta estructura/metadatos del archivo pueden seguir siendo visibles.

La inyección mediante `exec-env` evita que el programa necesite leer un archivo de credenciales en claro del repo y evita exportar las credenciales permanentemente a la shell del usuario. No significa que el secreto sea invisible durante el uso:

- El proceso que lo recibe y sus procesos descendientes pueden leer las variables.
- Herramientas de depuración, volcados de memoria, trazas o procesos del mismo usuario podrían exponer el entorno según la configuración del sistema.
- Si el programa imprime una variable, la credencial puede quedar en la terminal, logs, CI o capturas.
- No se debe afirmar que el secreto existe “solo en RAM” como garantía absoluta del sistema operativo.

Por eso, no imprimir secretos ni volcar el entorno completo forma parte del diseño de seguridad. La guía no reemplaza permisos correctos, control de acceso al equipo ni rotación de credenciales.

## 3. Roles, destinatarios y administración

Este esquema no contiene un servicio central de administración ni permisos por variable. El acceso criptográfico depende de quién posee la clave privada Age correspondiente:

1. El administrador/operador autorizado conserva y distribuye la clave privada fuera del repo mediante un canal seguro aprobado por el equipo.
2. El administrador obtiene el destinatario público Age para cifrar; la clave privada no se comparte en Git ni en mensajes, issues o prompts.
3. Los secretos se guardan en un archivo `.env` local temporal y se cifran con SOPS para ese destinatario. Se versiona únicamente el archivo cifrado.
4. Para dar acceso a otra persona o equipo, se debe verificar su identidad y añadir el destinatario público correcto, y volver a cifrar/actualizar el archivo con SOPS. Entregar la clave privada existente a más personas amplía el acceso a todo lo que esa clave pueda descifrar.
5. Ante pérdida o sospecha de exposición de la clave privada, hay que generar/emitir una nueva, volver a cifrar los secretos para los nuevos destinatarios y rotar también las credenciales externas comprometidas.

Cualquier persona que tenga una clave privada autorizada para el archivo puede descifrar los secretos que contiene. Separar privilegios por aplicación requiere separar archivos y/o destinatarios; no basta con que cada programa lea solo algunas variables.

## 4. Requisitos e instalación local en WSL

Instala `sops` y `age` en la distribución WSL que ejecuta los programas. Verifica que ambos comandos estén disponibles:

```bash
sops --version
age --version
```

La clave privada debe estar en el sistema de archivos Linux de WSL, con permisos restringidos. Si ya recibiste una clave privada por el canal seguro del equipo, colócala en la ruta acordada y aplica permisos restrictivos:

```bash
install -d -m 700 "$HOME/.config/sops/age"
chmod 600 "$HOME/.config/sops/age/keys.txt"
```

No reemplaces la clave privada existente generando una nueva sin coordinarlo: un destinatario distinto no podrá descifrar automáticamente los archivos cifrados para la clave anterior. Si se aprovisiona una clave nueva, `age-keygen` puede crearla y `age-keygen -y` puede mostrar su destinatario público; la privada debe permanecer fuera del repo y respaldarse de manera segura.

SOPS localiza la clave con `SOPS_AGE_KEY_FILE`. Se puede definir para una sola invocación (preferible para evitar dejar estado en la shell):

```bash
SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" sops exec-env secrets.enc.env "python3 app.py"
```

También se puede exportar `SOPS_AGE_KEY_FILE` durante una sesión de trabajo. No se debe exportar el valor de las credenciales AWS de forma permanente ni añadirlas al `.bashrc`.

## 5. Crear y actualizar el archivo cifrado

### Archivo de variables

El formato del ejemplo es dotenv: una asignación `NOMBRE=valor` por línea. Para AWS, el archivo puede contener variables como `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_DEFAULT_REGION`. Nunca escribas sus valores reales en código, documentación, comandos guardados, historial del shell ni archivos rastreados por Git.

Si el proyecto puede usar credenciales temporales, perfiles locales, roles o federación de identidad, prefiérelos a claves AWS de larga duración. Para Amazon Bedrock, utiliza el mecanismo de autenticación AWS recomendado para el entorno y concede únicamente los permisos y regiones necesarios. Los nombres anteriores son variables de entorno estándar que los SDK de AWS, incluido el usado por Python, suelen detectar automáticamente.

### Cifrado

Crea/edita el archivo en claro fuera del repositorio, con permisos privados, y cifra usando la clave pública Age del destinatario autorizado. El README del workspace muestra el comando SOPS usado para generar `secrets.enc.env`:

```bash
sops --age "$AGE_PUBLIC_RECIPIENT" --encrypt "$HOME/ruta-segura/secrets.env" > secrets.enc.env
```

`AGE_PUBLIC_RECIPIENT` representa el destinatario público aprobado (`age1...`), no una clave privada. No pongas el valor de un secreto en esta variable ni en la línea de comandos. No guardes el archivo sin cifrar bajo el workspace; la regla `*.env` de `.gitignore` es una protección adicional, no un mecanismo de cifrado ni garantía contra `git add -f`.

Para editar secretos de un archivo SOPS ya cifrado, usa el modo de edición de SOPS con la clave local, por ejemplo:

```bash
SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" sops secrets.enc.env
```

Comprueba que la operación terminó correctamente y que el archivo en el repo sigue cifrado. Nunca hagas `cat`, `echo`, `env`, `set -x` ni `grep` de valores descifrados para verificar credenciales. Si un archivo en claro se añadió o llegó a Git alguna vez, borrar la copia de trabajo no elimina el historial: considera la credencial expuesta, revócala/rótala y trata el historial según el procedimiento del equipo.

## 6. Ejecutar programas con secretos

La forma estándar es envolver el comando de inicio del programa con `sops exec-env` desde la raíz del repo. El ejemplo del workspace usa esta sintaxis:

```bash
SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" \
  sops exec-env secrets.enc.env "python3 app.py"
```

Reemplaza el comando interno por el ejecutable que corresponda. Ejemplos:

```bash
SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" sops exec-env secrets.enc.env "bash ./app.sh"
SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" sops exec-env secrets.enc.env "./mi_programa_c"
SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" sops exec-env secrets.enc.env "./mi_programa_cpp"
```

También se puede definir un alias local similar a `bashrc_ejemplo`, pero recuerda que el alias actual usa una ruta relativa a `secrets.enc.env`: ejecútalo desde la ubicación esperada o configúralo para el proyecto/ruta apropiados. Un script lanzador del proyecto suele ser más claro y reproducible que un alias personal.

### Python

El proceso lee las variables del entorno con `os.environ` o `os.getenv`. Debe validar que existan y fallar con un mensaje que nombre la variable faltante, sin incluir su valor. No necesita importar SOPS ni conocer la ruta de la clave privada; SOPS ya hizo la inyección antes de arrancar Python.

```python
import os

aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
aws_region = os.environ.get("AWS_DEFAULT_REGION")

if not aws_access_key_id or not aws_secret_access_key:
    raise RuntimeError("Faltan variables de autenticación AWS requeridas")
```

Pasa estas variables al SDK o cliente requerido sin imprimirlas, escribirlas a archivos ni incluirlas en excepciones/logs.

### C

Usa `getenv()` de `<stdlib.h>`. Comprueba el puntero antes de usarlo; no imprimas el contenido:

```c
#include <stdlib.h>

const char *aws_access_key_id = getenv("AWS_ACCESS_KEY_ID");
const char *aws_secret_access_key = getenv("AWS_SECRET_ACCESS_KEY");
const char *aws_region = getenv("AWS_DEFAULT_REGION");

if (aws_access_key_id == NULL || aws_secret_access_key == NULL) {
    /* Reportar que falta una variable, nunca su valor. */
    return 1;
}
```

### C++

Usa `std::getenv()` de `<cstdlib>`. Comprueba `nullptr` antes de construir objetos o llamar al cliente:

```cpp
#include <cstdlib>

const char* aws_access_key_id = std::getenv("AWS_ACCESS_KEY_ID");
const char* aws_secret_access_key = std::getenv("AWS_SECRET_ACCESS_KEY");
const char* aws_region = std::getenv("AWS_DEFAULT_REGION");

if (aws_access_key_id == nullptr || aws_secret_access_key == nullptr) {
    // Reportar que falta una variable, nunca su valor.
    return 1;
}
```

### Bash

Usa expansión segura para comprobar presencia bajo `set -u`; evita activar `set -x` mientras el entorno tenga secretos:

```bash
#!/usr/bin/env bash
set -euo pipefail

: "${AWS_ACCESS_KEY_ID:?Falta AWS_ACCESS_KEY_ID}"
: "${AWS_SECRET_ACCESS_KEY:?Falta AWS_SECRET_ACCESS_KEY}"
exec ./aplicacion
```

El programa recibe las variables porque es un proceso hijo. No es necesario ni conveniente mostrarlas con `echo`.

## 7. AWS Bedrock: patrón de integración

Una solicitud para integrar un programa Python que utiliza Bedrock debe seguir este flujo:

1. Identificar qué SDK/cliente y método de autenticación ya usa el proyecto; no introducir una nueva dependencia sin comprobar las existentes.
2. Usar variables AWS convencionales o el mecanismo de identidad recomendado por el entorno. Si se requieren claves estáticas, leerlas solo desde el entorno inyectado; nunca pegarlas en Python, `.env` versionado, configuración de VS Code o parámetros guardados.
3. Lanzar el programa bajo `sops exec-env secrets.enc.env "python3 ..."`.
4. Validar presencia y emitir errores sin valores. No imprimir el objeto completo de configuración ni habilitar logging HTTP que exponga `Authorization`/tokens.
5. Probar sin credenciales reales o con una identidad temporal/de mínimo privilegio; la suite no debe imprimir, persistir ni subir secretos.

El valor del secreto no debe incorporarse en el código para construir el cliente cuando el SDK ya puede descubrirlo desde el entorno.

## 8. No filtrar credenciales

No hagas lo siguiente:

- Imprimir valores o mostrar el entorno completo (`env`, `print(os.environ)`, `printf`, `std::cout`, etc.).
- Guardar el resultado descifrado de SOPS en el repo, artefactos, archivos temporales compartidos o logs.
- Activar trazas de shell (`set -x`) o logging/debug que capture variables, headers de autenticación o configuración completa.
- Pasar secretos como argumentos posicionales del programa: pueden aparecer en listados de procesos o logs. Usa las variables de entorno inyectadas.
- Poner la clave privada, su ruta respaldada dentro del repo o una credencial real en código, tests, documentación o historial Git.
- Confiar exclusivamente en `.gitignore`: revisa `git status` antes de commit y verifica los archivos nuevos/sospechosos antes de `git add`.

**Advertencia sobre los ejemplos actuales:** algunos programas de demostración (`01_simple.sh`, `02_script.sh`, `03_app.py`, `04_app.c` y `05_app.cpp`) imprimen variables o el entorno para mostrar la prueba. Sirven como demostración del acceso, pero ese comportamiento no es apropiado para programas reales y podría revelar credenciales en la terminal o en logs. Al reutilizarlos, elimina esas impresiones y registra solo presencia/ausencia.

## 9. Checklist al integrar un programa nuevo

- [ ] Las variables necesarias están definidas en el archivo SOPS cifrado; no hay valores reales en el código ni en archivos rastreados.
- [ ] El archivo privado `keys.txt` está fuera del repo y accesible solo al usuario WSL autorizado.
- [ ] La aplicación se inicia bajo `sops exec-env` con la ruta correcta al archivo cifrado.
- [ ] Python/C/C++/Bash consume las variables estándar del entorno y valida las requeridas.
- [ ] No se imprimen secretos, no se vuelca el entorno y no se activan trazas/logs sensibles.
- [ ] Los tests usan valores ficticios o una identidad controlada y no registran credenciales.
- [ ] Antes de commitear, se inspeccionan `git status` y los cambios para confirmar que solo se versiona ciphertext y código sin secretos.

## 10. Diagnóstico básico

- **SOPS no puede descifrar:** confirma que estás en WSL, que `SOPS_AGE_KEY_FILE` apunta a la clave privada correcta y que esa clave corresponde a un destinatario incluido en el archivo cifrado. No muestres ni compartas la clave.
- **Variable ausente:** confirma que su nombre coincide exactamente en el archivo cifrado y en el código; comprueba que el comando ejecutado realmente está envuelto con `sops exec-env`.
- **El programa funciona a mano pero falla bajo SOPS:** revisa ruta de trabajo, ruta del archivo cifrado y que el comando interno de `exec-env` sea el mismo ejecutable/configuración.
- **Una persona nueva no puede descifrar:** la clave privada no se recupera del ciphertext. El administrador debe verificar su destinatario y volver a cifrar para ese destinatario mediante el proceso acordado.

## 11. Archivos relevantes de este workspace

- `.gitignore`: ignora archivos `*.env` y claves seleccionadas; permite explícitamente `secrets.enc.env`. No es sustituto de revisar cada commit.
- `secrets.enc.env`: ejemplo versionable con contenido SOPS cifrado.
- `bashrc_ejemplo`: alias ilustrativo para ejecutar con `sops exec-env`.
- `01_simple.sh`, `02_script.sh`, `03_app.py`, `04_app.c`, `05_app.cpp`: ejemplos de consumo en Bash, Python, C y C++ (ver advertencia de impresiones).
- `test_01.sh` y `Makefile`: compilación y pruebas de ejemplo.
- `readme.md`: guía breve preexistente; este documento amplía el uso seguro y especifica el flujo para nuevos programas.

## Instrucción reutilizable para integrar un programa

Se puede usar el siguiente pedido al trabajar en una aplicación nueva o existente:

> Vamos a trabajar en el programa **[ruta/nombre del programa y lenguaje]**. Lee `11_doc/01_secrets_user_guide_wsl.md` y sigue el esquema SOPS + Age del workspace. Revisa primero cómo se inicia la aplicación, qué variables necesita y qué SDK/configuración ya existen. Modifica o prepara el programa para leer los secretos requeridos desde variables de entorno inyectadas por `sops exec-env` usando `secrets.enc.env`; no agregues valores reales, claves privadas ni archivos descifrados al repo. Valida variables faltantes sin imprimir valores, no vuelques el entorno ni habilites trazas/logging que revelen credenciales. Para AWS/Bedrock, usa el mecanismo de autenticación AWS apropiado y de mínimo privilegio. Añade o adapta pruebas sin credenciales reales y verifica que los cambios no incluyan secretos.

Al dar la instrucción para un programa real, especifica también los nombres de las variables requeridas y el comando de inicio esperado, pero nunca sus valores. Si el archivo cifrado, los destinatarios o la identidad local no están disponibles, detén la integración que dependa de ellos y solicita la configuración segura correspondiente; no inventes credenciales.
