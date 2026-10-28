# Sistema de Asistencias Facial

Primer hito del sistema de reconocimiento facial para la materia Ingeniería del Conocimiento. Se basa en el ZIP provisto por la cátedra y conserva los dos puntos de entrada solicitados:

- `reconocimiento_facial.py`: comparación de dos imágenes.
- `programa_asistencia.py`: reconocimiento continuo por webcam y registro CSV.

El núcleo está separado en `asistencia_facial/` para que el próximo hito pueda conectarlo a una interfaz web de garita sin duplicar la lógica de reconocimiento.

## Requisitos e instalación

Se requiere Python 3.12, una cámara compatible con OpenCV y `uv`.

```bash
uv sync
```

`face-recognition` usa `dlib`. La dependencia `setuptools<81` está fijada porque la versión actual de los modelos todavía importa `pkg_resources`.

## Comparar dos fotografías

Con los archivos de prueba incluidos:

```bash
uv run python reconocimiento_facial.py
```

Para indicar otros archivos o ejecutar sin ventanas:

```bash
uv run python reconocimiento_facial.py \
  --control assets/pruebas/FotoA.jpg \
  --prueba assets/pruebas/FotoC.jpg \
  --tolerancia 0.6 \
  --sin-ventanas
```

La salida informa si coincide y la distancia facial. Una distancia menor o igual a la tolerancia se considera coincidencia.

## Registrar asistencia con webcam

La ejecución abre la cámara predeterminada y termina con `Q` o `Esc`:

```bash
uv run python programa_asistencia.py --tipo entrada
uv run python programa_asistencia.py --tipo salida
```

Opciones útiles:

```text
--camara 0                 Índice de cámara OpenCV.
--empleados RUTA           Carpeta con una imagen por empleado.
--registro RUTA            CSV de salida; por defecto datos/registro.csv.
--tolerancia 0.6           Sensibilidad de la comparación.
--modelo hog|cnn           HOG es el valor recomendado para CPU.
--escala 0.25              Reducción del frame para acelerar la detección.
--sin-ventanas             Procesa hasta Ctrl+C sin abrir una ventana.
```

## Panel web local

El proyecto incluye una interfaz web local para operar la garita desde un navegador. No usa una base de datos: conserva las imágenes en `assets/empleados/` y continúa escribiendo las marcaciones en `datos/registro.csv`.

Antes de iniciar el panel, cambiá `WEB_PASSWORD` en `asistencia_facial/web.py`. La contraseña está hardcodeada únicamente para este prototipo local.

```bash
uv run asistencia-web
```

Abrí `http://127.0.0.1:5000/`, ingresá la contraseña y elegí entre:

- **Asistencia**: habilita la cámara del navegador solamente después de pulsar `Iniciar cámara`, permite marcar entrada o salida y muestra el resultado.
- **Registros**: muestra el contenido actual del CSV con filtros por empleado y tipo de evento, sin modificarlo.
- **Empleados**: muestra el padrón, permite cargar una imagen con exactamente un rostro y eliminar imágenes sin borrar los logs históricos.

La cámara del navegador debe habilitarse desde un contexto seguro. `localhost` funciona para el uso local; para acceder desde otro equipo será necesario configurar HTTPS.

Los nombres de las imágenes se convierten en identificadores estables. Por ejemplo, `Michio Kaku.jpg` produce `michio-kaku`. Cada imagen debe contener exactamente un rostro. Los archivos no compatibles se ignoran y las imágenes inválidas se informan como advertencias; si no queda ningún empleado válido, el programa termina.

## Registro CSV

El sistema crea `datos/registro.csv` al primer registro con esta cabecera:

```csv
id_empleado,nombre,fecha,hora,tipo,distancia
```

Se permite una `entrada` y una `salida` por empleado y fecha. Una segunda detección del mismo tipo se muestra como `ya registrado` y no agrega otra fila. El CSV original del ZIP queda en `material_catedra/registro_original.csv` porque usa un esquema anterior (`nombre, hora`).

## Pruebas

```bash
uv run pytest
```

Las pruebas incluyen el material real: las siete imágenes de empleados y las tres imágenes de prueba. En ese material, `FotoA` y `FotoB` coinciden con una distancia aproximada de `0.410`; `FotoA` y `FotoC` no coinciden con una distancia aproximada de `0.809`.

## Limitaciones del primer hito

Es una aplicación local y académica. El panel web usa una contraseña compartida hardcodeada, no tiene usuarios ni roles individuales, no incorpora cifrado propio ni detección de vida, y no debe exponerse a Internet sin una capa de seguridad adicional. Antes de utilizarla con guardias reales habría que incorporar esas protecciones, consentimiento y una auditoría de eventos. Las codificaciones faciales se calculan en memoria y no se guardan en disco.
