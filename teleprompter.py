#!/usr/bin/env python3
"""
Teleprompter Desktop
Ventana flotante, sin bordes, siempre al frente.

Modos de desplazamiento:
  VERTICAL    — texto sube de abajo hacia arriba (varias líneas)
  HORIZONTAL  — texto corre de derecha a izquierda en un solo renglón (ticker)

Controles:
  ESPACIO       — Pausar / Reanudar
  ↑ / ↓        — Aumentar / Reducir velocidad
  Rueda ratón   — Igual que ↑ / ↓
  M             — Cambiar modo (vertical ↔ horizontal)
  R             — Volver al inicio
  Q / Esc       — Salir
  Clic derecho  — Menú contextual
"""

import sys
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QTextEdit, QSpinBox, QSlider, QDialogButtonBox,
    QFileDialog, QMenu, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QBrush, QFontMetrics,
    QLinearGradient, QKeyEvent, QMouseEvent, QWheelEvent,
)


# ─── Parámetros globales ──────────────────────────────────────────────────────

TICK_MS  = 30    # intervalo del timer (~33 fps)
FADE_PX  = 48    # tamaño de la franja de fade en cada borde

DEFAULTS: dict = dict(
    text=(
        "Bienvenido al Teleprompter.\n\n"
        "Abre Configuración (clic derecho → Configurar)\n"
        "para pegar tu guion.\n\n"
        "Controles:\n"
        "  ESPACIO — Pausar / Reanudar\n"
        "  ↑ / ↓   — Más / Menos velocidad\n"
        "  M        — Cambiar modo vertical ↔ horizontal\n"
        "  R        — Volver al inicio\n"
        "  Q / Esc  — Salir"
    ),
    font_size  = 36,
    speed      = 3,        # 1-30; pixeles por tick × 0.5
    bg_opacity = 210,      # 0-255
    win_width  = 860,
    win_height = 190,
    mode       = "vertical",   # "vertical" | "horizontal"
)


# ─── Widget de texto con scroll ───────────────────────────────────────────────

class ScrollCanvas(QWidget):
    """
    Dibuja el guion y lo desplaza.
      Modo vertical   → líneas suben de abajo hacia arriba.
      Modo horizontal → una sola línea corre de derecha a izquierda (ticker).
    El fondo es transparente; el color de fondo lo pinta la ventana padre.
    """

    def __init__(self, bg_opacity: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # Estado compartido
        self._raw: str       = ""
        self._scroll: float  = 0.0
        self._fs: int        = DEFAULTS["font_size"]
        self._bg_alpha: int  = bg_opacity
        self._color          = QColor(255, 255, 255)
        self._mode: str      = DEFAULTS["mode"]
        # Fuente con fallback cross-platform
        self._font_families  = ["Segoe UI", "Ubuntu", "DejaVu Sans", "Sans Serif"]

        # Estado exclusivo de modo vertical
        self._lines: list    = []
        self._lh: int        = 50

        # Estado exclusivo de modo horizontal
        self._h_text: str    = ""
        self._h_width: int   = 0

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    # ── API pública ───────────────────────────────────────────────────────────

    def load(self, text: str, font_size: int, avail_width: int = 0, mode: str = "vertical"):
        self._raw    = text
        self._fs     = font_size
        self._mode   = mode
        self._scroll = 0.0
        width = avail_width if avail_width > 0 else max(self.width() - 32, 200)
        self._lines  = self._wrap(text, width)
        self._lh     = self._compute_lh()
        self._prepare_horizontal()
        self.update()

    def set_mode(self, mode: str):
        self._mode   = mode
        self._scroll = 0.0
        self.update()

    def set_bg_alpha(self, alpha: int):
        self._bg_alpha = alpha

    def advance(self, px: float) -> bool:
        """
        Avanza el scroll según el modo activo.
        Vertical   → devuelve True al llegar al final (para al acabar).
        Horizontal → siempre False; el texto hace loop automático.
        """
        if self._mode == "vertical":
            limit = max(0.0, len(self._lines) * self._lh - self.height() * 0.55)
            self._scroll = min(self._scroll + px, limit)
            self.update()
            return self._scroll >= limit
        else:
            # El loop ocurre cuando el texto ha cruzado completamente la pantalla
            cycle = self._h_width + self.width() + 60
            self._scroll = (self._scroll + px) % cycle
            self.update()
            return False

    def rewind(self):
        self._scroll = 0.0
        self.update()

    # ── Helpers de fuente y texto ─────────────────────────────────────────────

    def _make_font(self) -> QFont:
        f = QFont(self._font_families[0], self._fs, QFont.Weight.Bold)
        f.setFamilies(self._font_families)
        return f

    def _compute_lh(self) -> int:
        fm = QFontMetrics(self._make_font())
        return int(fm.height() * 1.45)

    def _wrap(self, text: str, max_w: int) -> list:
        """Word-wrap para modo vertical."""
        font = self._make_font()
        fm   = QFontMetrics(font)
        out  = []
        for para in text.split("\n"):
            if not para.strip():
                out.append("")
                continue
            line = ""
            for word in para.split():
                cand = (line + " " + word).lstrip()
                if fm.horizontalAdvance(cand) <= max_w:
                    line = cand
                else:
                    if line:
                        out.append(line)
                    line = word
            if line:
                out.append(line)
        return out

    def _prepare_horizontal(self):
        """Aplana el texto en un único renglón para el ticker."""
        parts = [l.strip() for l in self._raw.split("\n") if l.strip()]
        self._h_text  = "   ·   ".join(parts)
        fm             = QFontMetrics(self._make_font())
        self._h_width  = fm.horizontalAdvance(self._h_text)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        if self._mode == "vertical":
            self._paint_vertical()
        else:
            self._paint_horizontal()

    # — Modo vertical ──────────────────────────────────────────────────────────

    def _paint_vertical(self):
        if not self._lines:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._make_font())

        pad   = 16
        start = int(self.height() // 3 - self._scroll)
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        for i, line in enumerate(self._lines):
            y = start + i * self._lh
            if y + self._lh < 0 or y > self.height():
                continue
            # Sombra
            p.setPen(QColor(0, 0, 0, 180))
            p.drawText(QRect(pad + 2, y + 2, self.width() - pad * 2, self._lh), flags, line)
            # Texto
            p.setPen(self._color)
            p.drawText(QRect(pad, y, self.width() - pad * 2, self._lh), flags, line)

        # Fades superior e inferior
        self._draw_fade_v(p, leading=True)
        self._draw_fade_v(p, leading=False)
        p.end()

    def _draw_fade_v(self, p: QPainter, *, leading: bool):
        """leading=True → borde superior; leading=False → borde inferior."""
        y0 = 0 if leading else self.height() - FADE_PX
        y1 = FADE_PX if leading else self.height()
        g  = QLinearGradient(0, y0, 0, y1)
        g.setColorAt(0 if leading else 1, QColor(0, 0, 0, self._bg_alpha))
        g.setColorAt(1 if leading else 0, QColor(0, 0, 0, 0))
        p.fillRect(0, y0, self.width(), FADE_PX, QBrush(g))

    # — Modo horizontal (ticker) ───────────────────────────────────────────────

    def _paint_horizontal(self):
        if not self._h_text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = self._make_font()
        p.setFont(font)

        # Posición X: texto entra por la derecha y sale por la izquierda
        x = self.width() - int(self._scroll)

        # Rectángulo que cubre el ancho real del texto (puede ser mayor al widget)
        rect = QRect(x, 0, self._h_width + 10, self.height())
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        # Sombra
        p.setPen(QColor(0, 0, 0, 180))
        p.drawText(rect.translated(2, 2), flags, self._h_text)

        # Texto principal
        p.setPen(self._color)
        p.drawText(rect, flags, self._h_text)

        # Fades izquierdo y derecho
        self._draw_fade_h(p, leading=True)
        self._draw_fade_h(p, leading=False)
        p.end()

    def _draw_fade_h(self, p: QPainter, *, leading: bool):
        """leading=True → borde izquierdo (texto sale); leading=False → borde derecho (texto entra)."""
        x0 = 0 if leading else self.width() - FADE_PX
        x1 = FADE_PX if leading else self.width()
        g  = QLinearGradient(x0, 0, x1, 0)
        g.setColorAt(0 if leading else 1, QColor(0, 0, 0, self._bg_alpha))
        g.setColorAt(1 if leading else 0, QColor(0, 0, 0, 0))
        p.fillRect(x0, 0, FADE_PX, self.height(), QBrush(g))

    # ── Resize ────────────────────────────────────────────────────────────────

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self._raw:
            self._lines = self._wrap(self._raw, max(self.width() - 32, 200))
            self._lh    = self._compute_lh()
            self.update()


# ─── Diálogo de configuración ─────────────────────────────────────────────────

class ConfigDialog(QDialog):

    def __init__(self, cfg: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cfg = dict(cfg)
        self.setWindowTitle("Teleprompter — Configuración")
        self.setMinimumWidth(560)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        root.addWidget(QLabel("<b>Texto / Guion:</b>"))

        self.txt = QTextEdit()
        self.txt.setFont(QFont("Consolas", 10))
        self.txt.setMinimumHeight(200)
        self.txt.setPlaceholderText("Pega aquí tu guion…")
        self.txt.setPlainText(self._cfg.get("text", ""))
        root.addWidget(self.txt)

        btn_file = QPushButton("📂  Cargar desde archivo de texto (.txt / .md)…")
        btn_file.clicked.connect(self._load_file)
        root.addWidget(btn_file)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        # ── Modo de desplazamiento ────────────────────────────────────────────
        mode_box = QGroupBox()
        mode_lay = QHBoxLayout(mode_box)
        mode_lay.setContentsMargins(6, 4, 6, 4)

        self.rb_vertical   = QRadioButton("↑  Vertical  (abajo → arriba, varias líneas)")
        self.rb_horizontal = QRadioButton("←  Horizontal  (derecha → izquierda, un renglón)")
        self._btn_grp = QButtonGroup(self)
        self._btn_grp.addButton(self.rb_vertical,   0)
        self._btn_grp.addButton(self.rb_horizontal, 1)

        if self._cfg.get("mode", "vertical") == "horizontal":
            self.rb_horizontal.setChecked(True)
        else:
            self.rb_vertical.setChecked(True)

        mode_lay.addWidget(self.rb_vertical)
        mode_lay.addWidget(self.rb_horizontal)
        form.addRow("Modo:", mode_box)

        # ── Tamaño de fuente ──────────────────────────────────────────────────
        self.spin_fs = QSpinBox()
        self.spin_fs.setRange(14, 120)
        self.spin_fs.setSuffix(" px")
        self.spin_fs.setValue(self._cfg.get("font_size", DEFAULTS["font_size"]))
        form.addRow("Tamaño de fuente:", self.spin_fs)

        # ── Velocidad ─────────────────────────────────────────────────────────
        self.sld_spd = QSlider(Qt.Orientation.Horizontal)
        self.sld_spd.setRange(1, 30)
        self.sld_spd.setValue(self._cfg.get("speed", DEFAULTS["speed"]))
        self.sld_spd.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.sld_spd.setTickInterval(5)
        self.lbl_spd = QLabel(str(self.sld_spd.value()))
        self.lbl_spd.setFixedWidth(28)
        self.sld_spd.valueChanged.connect(lambda v: self.lbl_spd.setText(str(v)))
        row_spd = QHBoxLayout()
        row_spd.addWidget(self.sld_spd)
        row_spd.addWidget(self.lbl_spd)
        form.addRow("Velocidad inicial (1-30):", row_spd)

        # ── Opacidad ──────────────────────────────────────────────────────────
        self.sld_op = QSlider(Qt.Orientation.Horizontal)
        self.sld_op.setRange(40, 255)
        self.sld_op.setValue(self._cfg.get("bg_opacity", DEFAULTS["bg_opacity"]))
        self.lbl_op = QLabel(str(self.sld_op.value()))
        self.lbl_op.setFixedWidth(28)
        self.sld_op.valueChanged.connect(lambda v: self.lbl_op.setText(str(v)))
        row_op = QHBoxLayout()
        row_op.addWidget(self.sld_op)
        row_op.addWidget(self.lbl_op)
        form.addRow("Opacidad fondo (40-255):", row_op)

        # ── Tamaño de ventana ─────────────────────────────────────────────────
        self.spin_w = QSpinBox()
        self.spin_w.setRange(400, 1920)
        self.spin_w.setSuffix(" px")
        self.spin_w.setValue(self._cfg.get("win_width", DEFAULTS["win_width"]))
        form.addRow("Ancho de ventana:", self.spin_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(60, 600)
        self.spin_h.setSuffix(" px")
        self.spin_h.setValue(self._cfg.get("win_height", DEFAULTS["win_height"]))
        form.addRow("Alto de ventana:", self.spin_h)

        root.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir guion", "",
            "Archivos de texto (*.txt *.md);;Todos los archivos (*)"
        )
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    self.txt.setPlainText(f.read())
            except OSError as e:
                self.txt.setPlainText(f"Error al abrir el archivo:\n{e}")

    def result_cfg(self) -> dict:
        return dict(
            text       = self.txt.toPlainText(),
            font_size  = self.spin_fs.value(),
            speed      = self.sld_spd.value(),
            bg_opacity = self.sld_op.value(),
            win_width  = self.spin_w.value(),
            win_height = self.spin_h.value(),
            mode       = "horizontal" if self.rb_horizontal.isChecked() else "vertical",
        )


# ─── Ventana principal del teleprompter ───────────────────────────────────────

class Teleprompter(QWidget):

    def __init__(self):
        super().__init__()
        self._cfg: dict    = dict(DEFAULTS)
        self._speed: float = float(self._cfg["speed"])
        self._paused: bool = True
        self._drag_pos     = None

        self._init_window()
        self._init_ui()
        self._init_timer()

        QTimer.singleShot(0, lambda: self._open_config(first=True))

    # ── Inicialización ────────────────────────────────────────────────────────

    def _init_window(self):
        self.setWindowTitle("Teleprompter Desktop")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _init_ui(self):
        self.canvas = ScrollCanvas(self._cfg["bg_opacity"], self)

        self._bar = QWidget(self)
        self._bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        bar_lay = QHBoxLayout(self._bar)
        bar_lay.setContentsMargins(12, 0, 4, 2)

        self._lbl_status = QLabel()
        self._lbl_status.setStyleSheet(
            "color: rgba(255,255,255,130); font-size: 10px;"
        )
        bar_lay.addWidget(self._lbl_status, 1)

        self._btn_cfg = QPushButton("⚙", self)
        self._btn_cfg.setFixedSize(24, 20)
        self._btn_cfg.setStyleSheet(
            "QPushButton{"
            "  background: rgba(255,255,255,30); color: white;"
            "  border: none; border-radius: 3px; font-size: 13px;"
            "}"
            "QPushButton:hover{ background: rgba(255,255,255,70); }"
        )
        self._btn_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cfg.clicked.connect(self._open_config)

        self._update_status()

    def _init_timer(self):
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h  = self.width(), self.height()
        BAR_H = 22
        if hasattr(self, "canvas"):
            self.canvas.setGeometry(0, 0, w, h)
        if hasattr(self, "_bar"):
            self._bar.setGeometry(0, h - BAR_H, w - 30, BAR_H)
        if hasattr(self, "_btn_cfg"):
            self._btn_cfg.move(w - 28, h - BAR_H)

    def _place_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w = self._cfg["win_width"]
        h = self._cfg["win_height"]
        self.resize(w, h)
        self.move((screen.width() - w) // 2, 8)

    # ── Fondo ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(0, 0, 0, self._cfg["bg_opacity"])))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 10, 10)
        p.end()

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _tick(self):
        if not self._paused:
            self.canvas.advance(self._speed * 0.5)

    # ── Teclado ───────────────────────────────────────────────────────────────

    def keyPressEvent(self, ev: QKeyEvent):
        k = ev.key()
        if k == Qt.Key.Key_Space:
            self._toggle_pause()
        elif k == Qt.Key.Key_Up:
            self._speed = min(self._speed + 0.5, 15.0)
            self._update_status()
        elif k == Qt.Key.Key_Down:
            self._speed = max(self._speed - 0.5, 0.5)
            self._update_status()
        elif k == Qt.Key.Key_M:
            self._toggle_mode()
        elif k == Qt.Key.Key_R:
            self.canvas.rewind()
            self._update_status()
        elif k in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            QApplication.quit()

    def wheelEvent(self, ev: QWheelEvent):
        if ev.angleDelta().y() > 0:
            self._speed = min(self._speed + 0.5, 15.0)
        else:
            self._speed = max(self._speed - 0.5, 0.5)
        self._update_status()

    def _toggle_pause(self):
        self._paused = not self._paused
        self._update_status()

    def _toggle_mode(self):
        current = self._cfg.get("mode", "vertical")
        self._cfg["mode"] = "horizontal" if current == "vertical" else "vertical"
        self.canvas.set_mode(self._cfg["mode"])
        self._update_status()

    def _update_status(self):
        pause_icon = "⏸" if self._paused else "▶"
        mode_label = "← Horizontal" if self._cfg.get("mode") == "horizontal" else "↑ Vertical"
        self._lbl_status.setText(
            f"{pause_icon} {mode_label}  Vel:{self._speed:.1f}  "
            "│ SPC pausar │ ↑↓ vel │ M modo │ R inicio │ Q salir"
        )

    # ── Ratón ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
        elif ev.button() == Qt.MouseButton.RightButton:
            self._ctx_menu(ev.globalPosition().toPoint())

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._drag_pos is not None and (ev.buttons() & Qt.MouseButton.LeftButton):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    # ── Menú contextual ───────────────────────────────────────────────────────

    def _ctx_menu(self, pos: QPoint):
        m = QMenu(self)
        m.setStyleSheet(
            "QMenu{"
            "  background:#1c1c1c; color:#eee;"
            "  border:1px solid #444; border-radius:6px; padding:4px;"
            "}"
            "QMenu::item{ padding:5px 20px; border-radius:4px; }"
            "QMenu::item:selected{ background:#333; }"
            "QMenu::separator{ height:1px; background:#444; margin:3px 8px; }"
        )
        current_mode = self._cfg.get("mode", "vertical")
        mode_label   = "← Cambiar a Horizontal" if current_mode == "vertical" else "↑ Cambiar a Vertical"

        a_cfg   = m.addAction("⚙  Configurar…")
        a_mode  = m.addAction(f"⇄  {mode_label}")
        a_pause = m.addAction("⏸  Pausar / Reanudar")
        a_reset = m.addAction("↩  Volver al inicio")
        m.addSeparator()
        a_quit  = m.addAction("✕  Salir")

        chosen = m.exec(pos)
        if   chosen == a_cfg:   self._open_config()
        elif chosen == a_mode:  self._toggle_mode()
        elif chosen == a_pause: self._toggle_pause()
        elif chosen == a_reset: self.canvas.rewind()
        elif chosen == a_quit:  QApplication.quit()

    # ── Configuración ─────────────────────────────────────────────────────────

    def _open_config(self, first: bool = False):
        was_paused   = self._paused
        self._paused = True

        dlg      = ConfigDialog(self._cfg, self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted

        if accepted:
            self._cfg.update(dlg.result_cfg())
            self._speed = float(self._cfg["speed"])
            self.canvas.set_bg_alpha(self._cfg["bg_opacity"])

        if accepted or first:
            self._apply()

        if not first:
            self._paused = was_paused

        self._update_status()

    def _apply(self):
        self._place_window()
        self.canvas.load(
            self._cfg["text"],
            self._cfg["font_size"],
            self._cfg["win_width"] - 32,
            self._cfg.get("mode", "vertical"),
        )
        self.update()
        self.raise_()
        self.activateWindow()


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Teleprompter Desktop")
    app.setStyle("Fusion")

    win = Teleprompter()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
