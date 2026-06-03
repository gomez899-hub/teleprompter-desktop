# Teleprompter Desktop

Ventana flotante minimalista para leer guiones frente a la cámara, sin que parezca que desvías la mirada.

Diseñada para colocarse justo debajo de la lente de la webcam, siempre visible por encima de cualquier otra ventana.

---

## Características

- **Sin bordes** y **siempre al frente** — no se oculta al interactuar con otras aplicaciones
- **Fondo semitransparente** con esquinas redondeadas y opacidad configurable
- **Dos modos de desplazamiento:**
  - `↑ Vertical` — el texto sube línea a línea (estilo teleprompter clásico)
  - `← Horizontal` — el texto corre de derecha a izquierda en un solo renglón (estilo ticker de noticias)
- **Velocidad ajustable en tiempo real** sin pausar la reproducción
- **Arrastrable** — colócala exactamente debajo de tu cámara
- **Panel de configuración** para pegar el guion, ajustar fuente, velocidad y opacidad
- Compatible con **Windows, Ubuntu y macOS**

---

## Requisitos

- Python 3.10 o superior
- PyQt6

---

## Instalación

### Ubuntu / macOS

```bash
git clone https://github.com/TU_USUARIO/teleprompter-desktop.git
cd teleprompter-desktop
python3 -m venv venv
source venv/bin/activate
pip install PyQt6
```

### Windows

```powershell
git clone https://github.com/TU_USUARIO/teleprompter-desktop.git
cd teleprompter-desktop
python -m venv venv
venv\Scripts\activate
pip install PyQt6
```

---

## Uso

### Ubuntu / macOS

```bash
venv/bin/python3 teleprompter.py
```

### Windows

```powershell
venv\Scripts\python teleprompter.py
```

Al iniciar se abre el panel de configuración. Pega tu guion, elige el modo de desplazamiento, ajusta los parámetros y pulsa **OK**. La ventana se posiciona automáticamente en la parte superior central de la pantalla.

---

## Controles

| Tecla | Acción |
|---|---|
| `Espacio` | Pausar / Reanudar |
| `↑` / `↓` | Aumentar / Reducir velocidad |
| Rueda del ratón | Aumentar / Reducir velocidad |
| `M` | Cambiar modo (vertical ↔ horizontal) |
| `R` | Volver al inicio del guion |
| `Q` / `Esc` | Salir |
| Clic izquierdo + arrastrar | Mover la ventana |
| Clic derecho | Menú contextual |

---

## Panel de configuración

Accesible al inicio, con el botón `⚙` o haciendo clic derecho → **Configurar**.

| Opción | Descripción |
|---|---|
| Texto / Guion | Pega el texto o carga un archivo `.txt` / `.md` |
| Modo | Vertical (varias líneas) u Horizontal (un renglón) |
| Tamaño de fuente | 14 – 120 px |
| Velocidad inicial | 1 – 30 |
| Opacidad del fondo | 40 (casi transparente) – 255 (negro sólido) |
| Ancho / Alto | Dimensiones de la ventana en píxeles |

---

## Estructura del proyecto

```
teleprompter-desktop/
├── teleprompter.py    # Aplicación completa
├── requirements.txt   # Dependencias (PyQt6)
└── README.md
```
