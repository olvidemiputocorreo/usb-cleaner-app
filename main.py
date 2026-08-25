import sys
import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QMessageBox, QProgressBar, QTableWidget, 
                             QTableWidgetItem, QCheckBox, QScrollArea)
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

class DuplicadosThread(QThread):
    progreso = pyqtSignal(int)
    duplicados_encontrados = pyqtSignal(list)
    finalizado = pyqtSignal(str)
    
    def __init__(self, ruta):
        super().__init__()
        self.ruta = ruta
    
    def calcular_hash(self, archivo):
        """Calcula el hash SHA256 de un archivo"""
        sha256 = hashlib.sha256()
        try:
            with open(archivo, 'rb') as f:
                for bloque in iter(lambda: f.read(4096), b''):
                    sha256.update(bloque)
            return sha256.hexdigest()
        except:
            return None
    
    def run(self):
        self.progreso.emit(0)
        self.progreso.emit(10)
        self.progreso.emit("Buscando duplicados...")
        
        archivos_hash = {}
        duplicados = []
        
        try:
            archivos = list(Path(self.ruta).rglob("*"))
            total = len(archivos)
            
            for idx, item in enumerate(archivos):
                if item.is_file():
                    try:
                        hash_archivo = self.calcular_hash(str(item))
                        if hash_archivo:
                            if hash_archivo in archivos_hash:
                                # Ya existe, es un duplicado
                                archivo_viejo = archivos_hash[hash_archivo]
                                archivo_nuevo = item
                                
                                # Determinar cuál es más antiguo
                                fecha_viejo = datetime.fromtimestamp(archivo_viejo['stat'].st_mtime)
                                fecha_nuevo = datetime.fromtimestamp(archivo_nuevo.stat().st_mtime)
                                
                                if fecha_viejo < fecha_nuevo:
                                    eliminar = archivo_viejo['ruta']
                                    mantener = str(archivo_nuevo)
                                else:
                                    eliminar = str(archivo_nuevo)
                                    mantener = archivo_viejo['ruta']
                                
                                duplicados.append({
                                    'mantener': mantener,
                                    'eliminar': eliminar,
                                    'tamaño': archivo_nuevo.stat().st_size / (1024 * 1024),
                                    'hash': hash_archivo
                                })
                            else:
                                archivos_hash[hash_archivo] = {
                                    'ruta': str(item),
                                    'stat': item.stat()
                                }
                    except:
                        pass
                
                progreso = int((idx / total) * 90) + 10
                self.progreso.emit(progreso)
            
            self.progreso.emit(100)
            self.duplicados_encontrados.emit(duplicados)
            
            if duplicados:
                total_mb = sum(d['tamaño'] for d in duplicados)
                self.finalizado.emit(f"✅ Se encontraron {len(duplicados)} duplicados ({total_mb:.2f} MB)")
            else:
                self.finalizado.emit("No se encontraron duplicados")
        except Exception as e:
            self.finalizado.emit(f"Error: {str(e)}")

class USBCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.duplicados_lista = []
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("🧹 USB Cleaner Pro")
        self.setGeometry(100, 100, 800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        
        # Título
        titulo = QLabel("USB CLEANER - Limpiador Inteligente de USB")
        titulo.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(titulo)
        
        # Selector USB
        usb_layout = QHBoxLayout()
        usb_layout.addWidget(QLabel("Unidad USB:"))
        self.usb_combo = QComboBox()
        self.cargar_usb()
        usb_layout.addWidget(self.usb_combo)
        layout.addLayout(usb_layout)
        
        # Botones principales
        btn_layout = QHBoxLayout()
        
        btn_temp = QPushButton("🗑️ Limpiar Temp")
        btn_temp.clicked.connect(self.limpiar_temp)
        btn_layout.addWidget(btn_temp)
        
        btn_grande = QPushButton("📁 Archivos Grandes")
        btn_grande.clicked.connect(self.mostrar_grandes)
        btn_layout.addWidget(btn_grande)
        
        btn_duplicados = QPushButton("🔍 Buscar Duplicados")
        btn_duplicados.clicked.connect(self.buscar_duplicados)
        btn_layout.addWidget(btn_duplicados)
        
        layout.addLayout(btn_layout)
        
        # Tabla de duplicados
        self.tabla_duplicados = QTableWidget()
        self.tabla_duplicados.setColumnCount(4)
        self.tabla_duplicados.setHorizontalHeaderLabels(["✓", "Archivo a Eliminar", "Tamaño (MB)", "Mantener"])
        self.tabla_duplicados.setVisible(False)
        layout.addWidget(self.tabla_duplicados)
        
        # Botones de duplicados
        self.btn_eliminar_duplicados = QPushButton("🗑️ Eliminar Seleccionados")
        self.btn_eliminar_duplicados.clicked.connect(self.eliminar_duplicados_seleccionados)
        self.btn_eliminar_duplicados.setVisible(False)
        layout.addWidget(self.btn_eliminar_duplicados)
        
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
    
    def buscar_duplicados(self):
        usb = self.obtener_usb_seleccionada()
        self.progreso.setVisible(True)
        self.status.setText("Buscando duplicados... (esto puede tardar)")
        self.tabla_duplicados.setVisible(False)
        self.btn_eliminar_duplicados.setVisible(False)
        
        self.thread = DuplicadosThread(usb)
        self.thread.progreso.connect(self.actualizar_progreso)
        self.thread.duplicados_encontrados.connect(self.mostrar_duplicados)
        self.thread.finalizado.connect(self.limpieza_finalizada)
        self.thread.start()
    
    def actualizar_progreso(self, valor):
        if isinstance(valor, int):
            self.progreso.setValue(valor)
        else:
            self.status.setText(valor)
    
    def mostrar_duplicados(self, duplicados):
        self.duplicados_lista = duplicados
        self.tabla_duplicados.setRowCount(0)
        
        for idx, dup in enumerate(duplicados):
            self.tabla_duplicados.insertRow(idx)
            
            # Checkbox (seleccionado por defecto)
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.tabla_duplicados.setCellWidget(idx, 0, checkbox)
            
            # Archivo a eliminar
            item_eliminar = QTableWidgetItem(Path(dup['eliminar']).name)
            self.tabla_duplicados.setItem(idx, 1, item_eliminar)
            
            # Tamaño
            item_tamaño = QTableWidgetItem(f"{dup['tamaño']:.2f} MB")
            self.tabla_duplicados.setItem(idx, 2, item_tamaño)
            
            # Archivo a mantener
            item_mantener = QTableWidgetItem(Path(dup['mantener']).name)
            self.tabla_duplicados.setItem(idx, 3, item_mantener)
        
        self.tabla_duplicados.setVisible(True)
        self.btn_eliminar_duplicados.setVisible(True)
    
    def eliminar_duplicados_seleccionados(self):
        seleccionados = []
        for idx in range(self.tabla_duplicados.rowCount()):
            checkbox = self.tabla_duplicados.cellWidget(idx, 0)
            if checkbox.isChecked():
                seleccionados.append(self.duplicados_lista[idx]['eliminar'])
        
        if not seleccionados:
            QMessageBox.warning(self, "Aviso", "Selecciona al menos un archivo para eliminar")
            return
        
        respuesta = QMessageBox.question(self, "Confirmar", 
                                        f"¿Eliminar {len(seleccionados)} archivos duplicados?")
        if respuesta == QMessageBox.StandardButton.Yes:
            bytes_liberados = 0
            for archivo in seleccionados:
                try:
                    tamaño = Path(archivo).stat().st_size
                    Path(archivo).unlink()
                    bytes_liberados += tamaño
                except Exception as e:
                    self.status.setText(f"Error eliminando {archivo}: {e}")
            
            mb = bytes_liberados / (1024 * 1024)
            QMessageBox.information(self, "Éxito", f"✅ Liberados: {mb:.2f} MB")
            self.tabla_duplicados.setVisible(False)
            self.btn_eliminar_duplicados.setVisible(False)
            self.status.setText("Listo")
    
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
