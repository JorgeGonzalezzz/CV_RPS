



## 📁 src/

Esta carpeta contiene toda la lógica principal del proyecto, incluyendo el flujo del juego, visión por computadora, seguridad, voz y visualización de resultados.

---

### `game.py`
Archivo central del proyecto.  
Controla el ciclo completo del juego de **Piedra, Papel o Tijeras**, incluyendo:
- Captura de video desde cámara local o stream
- Coordinación del tracker y el visualizador
- Gestión de rondas y puntuaciones
- Sistema de contraseña gestual
- Feedback por voz
- Guardado de resultados y lanzamiento del dashboard final

Es el punto de entrada principal de la lógica del juego.

---

### `tracker.py`
Encargado del **seguimiento de manos y reconocimiento de gestos** mediante visión por computadora:
- Segmentación por color en espacio HSV
- Seguimiento de posición con filtro de Kalman
- Reconocimiento de gestos (ROCK / PAPER / SCISSORS) usando contornos y convexidad
- Suavizado temporal de gestos para reducir ruido
- Visualización de bounding boxes, centros y etiquetas

Incluye también `TrackerVisualizer`, responsable del renderizado gráfico.

---

### `game_info.py`
Gestiona el **estado interno del juego y los resultados**:
- Historial completo de rondas
- Cálculo de ganadores según las reglas RPS
- Control del marcador (victorias, empates y nulos)
- Exportación de resultados a disco (frames, máscaras y `summary.json`)

Es la fuente de datos para el dashboard de resultados.

---

### `dashboard.py`
Dashboard interactivo basado en **Flask** para visualizar los resultados del juego:
- Marcador final
- Resumen de rondas
- Navegación por imágenes y máscaras generadas
- Interfaz web ligera para análisis post-partida

Se ejecuta automáticamente al finalizar la partida (si está habilitado).

---

### `password_lock.py`
Implementa un **sistema de bloqueo por contraseña gestual** antes de iniciar el juego:
- Requiere una secuencia específica de pares de gestos
- Maneja estados internos (ARM, SELECT, CONFIRM, DONE)
- Incluye control de errores y reinicios automáticos
- Proporciona feedback visual del estado del bloqueo

Previene inicios accidentales y añade una capa de seguridad.

---

### `voice.py`
Módulo de **texto a voz (TTS)** no bloqueante usando `pyttsx3`:
- Anuncia instrucciones del juego y estados importantes
- Funciona de forma asíncrona para no bloquear la interfaz
- Se desactiva automáticamente si el sistema no soporta TTS

Mejora la experiencia de usuario durante la partida.

---

### `undistort.py`
Módulo para la **corrección de distorsión de lente** de la cámara:
- Usa parámetros de calibración almacenados en archivos `.npz`
- Permite controlar el recorte de imagen y el campo de visión
- Se aplica antes del tracking para mejorar la precisión del reconocimiento

Especialmente útil para cámaras gran angulares o móviles.

---

## 📁 calibration_notebooks/

Esta carpeta contiene **notebooks auxiliares** utilizados durante la fase de calibración y pruebas del sistema.  
No son necesarios para ejecutar el juego, pero **sí son clave para configurar correctamente la cámara y los colores** antes de jugar.

---

### `calibrate_camera.ipynb`
Notebook para la **calibración de la cámara** usando un tablero de ajedrez (chessboard):

- Captura múltiples imágenes del tablero desde distintos ángulos
- Detecta esquinas del patrón
- Calcula la matriz intrínseca de la cámara (`K`) y los coeficientes de distorsión
- Exporta los parámetros de calibración a un archivo `.npz`

Estos datos se utilizan posteriormente por `undistort.py` para corregir la distorsión de lente.

---

### `calibrate_colors.ipynb`
Notebook para la **calibración de colores en HSV** usados en el tracking de manos:

- Carga imágenes de prueba de manos (por ejemplo, guantes rojo y azul)
- Permite ajustar rangos HSV de forma interactiva
- Ayuda a definir los valores `lower` y `upper` que luego se guardan en los archivos de configuración
- Facilita una segmentación robusta bajo distintas condiciones de iluminación

Es fundamental para que el tracker detecte correctamente cada jugador.

---

### 📁 `chessboard/`
Conjunto de imágenes del **tablero de ajedrez** usadas como entrada para la calibración de cámara:
- Muestran el patrón desde diferentes posiciones y rotaciones
- Se usan directamente en `calibrate_camera.ipynb`

---

### 📁 `output/initial_corners/`
Resultados intermedios de la calibración de cámara:
- Imágenes con las esquinas del tablero detectadas y dibujadas
- Útiles para verificar visualmente que la detección es correcta antes de calcular la calibración final

---

### 📁 `hands/test_hands_3/`
Imágenes de prueba para calibración y validación del tracking de color:
- Carpeta `blue/`: ejemplos de la mano del jugador azul
- Carpeta `red/`: ejemplos de la mano del jugador rojo

Se utilizan principalmente en `calibrate_colors.ipynb`.

---

ℹ️ **Nota**  
Estos notebooks están pensados como herramientas de soporte y experimentación.  
Una vez calibrado el sistema y generados los archivos necesarios (`.npz`, rangos HSV), **no es necesario volver a ejecutarlos** para jugar.

---

## 📁 configs/

Esta carpeta contiene **archivos de configuración persistente** utilizados por el sistema en tiempo de ejecución.  
Aquí se pueden **guardar los parámetros obtenidos a partir de los notebooks de calibración**, de forma que no sea necesario recalibrar cada vez que se ejecuta el juego.

---

### `calibration_phone.npz`
Archivo de **calibración de cámara** generado desde `calibrate_camera.ipynb`.

Contiene:
- Matriz intrínseca de la cámara (`K`)
- Coeficientes de distorsión (`dist`)

Este archivo es consumido directamente por el módulo `undistort.py` para corregir la distorsión de lente antes del tracking.

📌 Este archivo permite reutilizar la calibración sin volver a ejecutar el notebook.

---

### `test_set.json`
Archivo de configuración de **rangos HSV para segmentación de color**.

Define, para cada jugador (por ejemplo `blue` y `red`):
- Valores `lower` y `upper` en espacio HSV

Estos parámetros suelen obtenerse y ajustarse en `calibrate_colors.ipynb`, y luego se guardan aquí para su uso directo por el tracker.

---

### `test_set_2.json`
Variación alternativa de configuración HSV:
- Útil para probar diferentes condiciones de iluminación
- Permite comparar estabilidad del tracking sin modificar código

---

### `test_set_3.json`
Otra variante de configuración de colores:
- Ajustes más estrictos o más permisivos según el entorno
- Facilita el cambio rápido de presets de calibración

---

ℹ️ **Nota importante**  
Los notebooks de calibración (`calibrate_camera.ipynb` y `calibrate_colors.ipynb`) están pensados para **generar y afinar estos parámetros**, pero **los valores finales deben guardarse en esta carpeta (`configs/`)** para que el sistema los cargue automáticamente durante la ejecución del juego.

Esto separa claramente:
- **Fase de calibración** (notebooks)
- **Fase de ejecución** (configuración persistente)

---

## 📁 web/

Esta carpeta proporciona el **soporte web para el dashboard de resultados**.  
Es utilizada directamente por `dashboard.py` (Flask) para renderizar la interfaz gráfica que permite inspeccionar las partidas jugadas.

---

### 📁 `templates/`

Contiene las **plantillas HTML** usadas por Flask.

#### `dashboard.html`
Plantilla principal del **RPS Results Dashboard**.  
Define toda la estructura de la interfaz web:

- Vista de ganador final y marcador
- Navegación por pestañas (Score / Frames / Masks)
- Visualización de frames de detección por ronda
- Visualización de máscaras (`mask_all`, `mask_red`, `mask_blue`)
- Navegación por teclado y botones (← / →, A / D, Home / End)

Recibe los datos directamente desde Flask (`players`, `rounds`, `final_score`, etc.) y los maneja con JavaScript embebido.

---

### 📁 `static/`

Contiene los **recursos estáticos** del dashboard.

#### `styles.css`
Hoja de estilos principal del dashboard:
- Tema oscuro moderno
- Diseño responsive
- Estilos para tarjetas, pestañas, botones y visores de imágenes
- Mejora la legibilidad y experiencia de análisis post-partida

Este archivo se carga automáticamente desde Flask y no requiere compilación adicional.

---

ℹ️ **Nota**  
La carpeta `web/` no contiene lógica de juego.  
Su único propósito es **dar soporte visual al dashboard**, permitiendo explorar de forma clara y cómoda los resultados exportados al finalizar una partida.

El dashboard se lanza automáticamente desde `game.py` cuando:
- La exportación de resultados está habilitada
- El módulo `dashboard.py` está disponible

---

## Ejecutables
Estos archivos completan el proyecto y sirven como **puntos de entrada**, **notebooks de prueba** y **herramientas de experimentación**.

---

### `main.py`
Punto de entrada principal para ejecutar el juego desde Python.

Funciones principales:
- Carga la configuración de colores desde `configs/`
- Carga los parámetros de calibración de cámara (`.npz`)
- Configura la fuente de cámara (webcam local o IP camera)
- Inicializa el `Game` con todos los parámetros necesarios
- Lanza la ejecución del juego

Es el archivo que debe ejecutarse para jugar una partida completa.

---

### `game.ipynb`
Notebook interactivo para **probar y depurar el flujo del juego**:

- Permite ejecutar el juego paso a paso
- Facilita pruebas rápidas sin usar la línea de comandos
- Útil para desarrollo, debugging y ajustes finos

No es necesario para la ejecución final del sistema.

---

### `tracker.ipynb`
Notebook de experimentación para el **sistema de tracking**:

- Pruebas aisladas del tracker de manos
- Visualización directa de máscaras, bounding boxes y gestos
- Ajuste fino de parámetros del reconocimiento de gestos

Pensado como herramienta de desarrollo y validación.


