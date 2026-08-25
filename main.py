import sys
import os
import shutil
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QMessageBox, QProgressBar
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import psutil

class LimpiarThread(QThread):
    progreso = pyqtSignal(int)
    mensaje = pyqtSignal(str)
    finalizado = pyqtSignal(str)
    
    def __init__(self, ruta, modo):
        super().__init__()
        self.ruta = ruta
        self.modo = modo
    
    def run(self):
        try:
            if self.modo == "temp":
                self.limpiar_temp()
            elif self.modo == "grande":
                self.encontrar_grandes()
        except Exception as e:
            self.finalizado.emit(f"Error: {str(e)}")
    
    def limpiar_temp(self):
        rutas_temp = [
            Path(self.ruta) / "System Volume Information",
            Path(self.ruta) / "$Recycle.Bin",
        ]
        
        bytes_liberados = 0
        for ruta in rutas_temp:
            if ruta.exists():
                try:
                    for item in ruta.rglob("*"):
                        if item.is_file():
                            bytes_liberados += item.stat().st_size
                            item.unlink()
                    self.mensaje.emit(f"Limpiada: {ruta.name}")
                except:
                    pass
        
        mb = bytes_liberados / (1024 * 1024)
        self.finalizado.emit(f"✅ Liberados: {mb:.2f} MB")
    
    def encontrar_grandes(self):
        self.mensaje.emit("Buscando archivos grandes...")
        grandes = []
        
        for item in Path(self.ruta).rglob("*"):
            if item.is_file():
                try:
                    tamaño = item.stat().st_size
                    if tamaño > 10 * 1024 * 1024:  # > 10 MB
                        grandes.append((str(item), tamaño / (1024 * 1024)))
                except:
                    pass
        
        if grandes:
            mensaje = "Archivos grandes encontrados:\n\n"
            for ruta, tamaño in sorted(grandes, key=lambda x: x[1], reverse=True)[:10]:
                mensaje += f"{Path(ruta).name}: {tamaño:.2f} MB\n"
            self.finalizado.emit(mensaje)
        else:
            self.finalizado.emit("No se encontraron archivos grandes")

class USBCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("🧹 USB Cleaner")
        self.setGeometry(100, 100, 600, 400)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        
        # Título
        titulo = QLabel("USB CLEANER - Limpiador de USB")
        titulo.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(titulo)
        
        # Selector USB
        usb_layout = QHBoxLayout()
        usb_layout.addWidget(QLabel("Unidad USB:"))
        self.usb_combo = QComboBox()
        self.cargar_usb()
        usb_layout.addWidget(self.usb_combo)
        layout.addLayout(usb_layout)
        
        # Botones
        btn_layout = QHBoxLayout()
        
        btn_temp = QPushButton("🗑️ Limpiar Temp")
        btn_temp.clicked.connect(self.limpiar_temp)
        btn_layout.addWidget(btn_temp)
        
        btn_grande = QPushButton("📁 Archivos Grandes")
        btn_grande.clicked.connect(self.mostrar_grandes)
        btn_layout.addWidget(btn_grande)
        
        layout.addLayout(btn_layout)
        
        # Barra de progreso
        self.progreso = QProgressBar()
        self.progreso.setVisible(False)
        layout.addWidget(self.progreso)
        
        # Status
        self.status = QLabel("Listo")
        self.status.setFont(QFont("Arial", 10))
        layout.addWidget(self.status)
        
        layout.addStretch()
        main_widget.setLayout(layout)
    
    def cargar_usb(self):
        try:
            for partition in psutil.disk_partitions():
                self.usb_combo.addItem(partition.mountpoint)
            # Agregar carpeta de prueba
            self.usb_combo.addItem("C:\\Users\\olvid\\Desktop\\USB-Cleaner-app\\test_usb")
        except:
            self.usb_combo.addItem("C:\\")
    
    def obtener_usb_seleccionada(self):
        return self.usb_combo.currentText()
    
    def limpiar_temp(self):
        usb = self.obtener_usb_seleccionada()
        respuesta = QMessageBox.question(self, "Confirmar", f"¿Limpiar archivos temporales en {usb}?")
        if respuesta == QMessageBox.StandardButton.Yes:
            self.progreso.setVisible(True)
            self.thread = LimpiarThread(usb, "temp")
            self.thread.mensaje.connect(self.actualizar_status)
            self.thread.finalizado.connect(self.limpieza_finalizada)
            self.thread.start()
    
    def mostrar_grandes(self):
        usb = self.obtener_usb_seleccionada()
        self.progreso.setVisible(True)
        self.status.setText("Buscando...")
        self.thread = LimpiarThread(usb, "grande")
        self.thread.finalizado.connect(self.limpieza_finalizada)
        self.thread.start()
    
    def actualizar_status(self, mensaje):
        self.status.setText(mensaje)
    
    def limpieza_finalizada(self, mensaje):
        self.progreso.setVisible(False)
        QMessageBox.information(self, "Resultado", mensaje)
        self.status.setText("Listo")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = USBCleaner()
    window.show()
    sys.exit(app.exec())
