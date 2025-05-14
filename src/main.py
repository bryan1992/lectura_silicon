import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QComboBox, QLabel, QPushButton, QWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter
import pyqtgraph as pg
from serial import Serial
import serial.tools.list_ports
import numpy as np
import time
from queue import Queue
from PyQt6 import QtGui

class ComboBoxDinamico (QComboBox):
    def __init__(self, parent = None):
        super().__init__(parent)

    def showPopup(self):
            self.actualizar_puertos_com()
            super().showPopup()

    def actualizar_puertos_com(self):
        puertos = serial.tools.list_ports.comports()
        self.clear()
        for puerto in puertos:
            self.addItem(puerto.device)
       
class MatrizRapida(QWidget):
    def __init__(self, parent = None, filas = 20, columnas = 8, tam_celda: int = 20):
        super().__init__(parent)
        self.filas = filas
        self.columnas = columnas
        self.tam_celda = tam_celda

        self.label = QLabel(self)
        self.label.setGeometry(0, 0, columnas * tam_celda, filas * tam_celda)

        self.imagen = QImage(columnas * tam_celda, filas * tam_celda, QImage.Format.Format_RGB32)
        self.imagen.fill(Qt.GlobalColor.black)
        
        painter = QPainter(self.imagen)
        for fila in range(filas):
            for columna in range(columnas):
                rect_x = columna * tam_celda
                rect_y = fila * tam_celda
                painter.fillRect(rect_x, rect_y, tam_celda, tam_celda, QColor("gray"))
                # Opcional: dibujar borde
                painter.setPen(QColor("black"))
                painter.drawRect(rect_x, rect_y, tam_celda - 1, tam_celda -1)
        painter.end()

        self.label.setPixmap(QPixmap.fromImage(self.imagen))

    def actualizar(self, matriz_bits: np.ndarray):
        painter = QPainter(self.imagen)
        for fila in range(min(self.filas, matriz_bits.shape[0])):
            for columna in range(min(self.columnas, matriz_bits.shape[1])):
                x = columna * self.tam_celda
                y = fila * self.tam_celda
                color = Qt.GlobalColor.green if matriz_bits[fila, columna] else Qt.GlobalColor.gray
                painter.fillRect(x, y, self.tam_celda, self.tam_celda, color)
                painter.setPen(QColor("gray"))
                painter.drawRect(x, y, self.tam_celda - 1, self.tam_celda - 1)
        painter.end()
        self.label.setPixmap(QPixmap.fromImage(self.imagen))


class HiloSerial(QThread): # Hilo para recibir datos mediante RS-232.
    
    def __init__(self, puerto_serial, cola_datos):
        super().__init__()
        self.serial_port = puerto_serial
        self.cola = cola_datos
        self._activo = True

    def run(self):
        # Enviar comando AT + esperar 200 ms
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.write(b'AT\n')
            time.sleep(0.2)

        while self._activo:
            if self.serial_port.in_waiting > 100:
                try:
                    # Datos en crudo del buffer serial.
                    datos = self.serial_port.read(self.serial_port.in_waiting)
                    self.cola.put(datos) # Se ponen los datos crudos en la cola.
                except Exception as e:
                    print(f"Error de comunicación: {e}")
                    self._activo = False
            time.sleep(0.1) # Delay de 100 mseg. para no saturar el CPU.

    def detener(self):
        self._activo = False

class HiloProcesamiento (QThread): # Hilo para procesar datos crudos.
    senal_procesada = pyqtSignal(object)    

    def __init__(self, cola_datos, parent = None):
        super().__init__(parent)
        self._activo = True
        self.cola = cola_datos

    def run(self):
        while self._activo:
            if not self.cola.empty():
                dato_crudo = self.cola.get()
                resultado = self.procesar_dato(dato_crudo)
                self.senal_procesada.emit(resultado)
                time.sleep(0.1)
    
    def procesar_dato(self, dato_crudo: bytes, delimitador: int = 10):
        
            # Convertir los datos crudos a un array Numpy de enteros (uint8)
            arreglo_uint8 = np.frombuffer(dato_crudo, dtype = np.uint8)

            # Obtener las posiciones de los delimitadores, el resultado es un array Numpy.
            indices = np.where(arreglo_uint8 == delimitador)[0]

            if len(indices) == 0:
                return[] #No hay ningún delimitador.
            
            segmentos = [] # Lista vacía de Python, no es un arreglo de Numpy.
            inicio = 0
            for fin in indices: # Segmentación de arreglo Numpy en una lista.
                if inicio > fin:
                    segmento = arreglo_uint8[inicio:fin]
                    segmentos.append(segmento) # Lista donde cada elemento es un arreglo de Numpy.
                inicio = fin + 1
            
            if len(segmentos) >= 3:
                # Reemplazar extremos de la lista
                segmentos[0] = segmentos[1]
                segmentos[-1] = segmentos[-2]

            return segmentos
  
    def detener(self):
        self._activo = False

class HiloMatrizBits(QThread): # Hilo para convertir datos procesados en matriz de booleanos.
    senal_matriz_bits = pyqtSignal(object)

    def __init__(self): #dato
        super().__init__()
        self._activo = True
        self.datos = None
        self.lock = QMutex()

    def run(self):
        while self._activo:
            self.lock.lock()
            if self.datos is not None:
                matriz = self.generar_matriz_booleanos(self.datos)
                self.datos = None
                self.senal_matriz_bits.emit(matriz)
            self.lock.unlock()
            self.msleep(50) # Espera para no saturar el CPU.


    def recibir_dato(self, datos):
        self.lock.lock()
        self.datos = datos
        self.lock.unlock()

    def generar_matriz_booleanos(self, segmentos):
        # Matriz de booleanos.
        # Inicializar lista de bits.
        lista_bits = []

        for segmento in segmentos:
            if len(segmento) > 4:
                byte = segmento[4] # Escalar de tipo uint8.
                bits = np.unpackbits(np.array([byte], dtype=np.uint8)) # Se convierte el escalar a un arreglo de un byte, después a un arreglo Numpy de 8 bits. 
                lista_bits.append(bits) # Lista de arreglos Numpy
        
        matriz = np.array(lista_bits, dtype= bool)
        return matriz
    
    def detener(self):
        self._activo = False

class HiloGrafica(QThread): # Hilo para convertir datos procesados en una gráfica.
    senal_grafica = pyqtSignal(object)

    def __init__(self): #datos
        super().__init__()
        self._activo = True
        self.datos = None

    def run(self):
        while self._activo:
            if self.datos is not None:
                eje_x, datos = self.generar_grafica(self.datos)
                self.senal_grafica.emit((eje_x, datos))
            self.msleep(100)

    def recibir_dato(self, datos):
        self.datos = datos

    def generar_grafica(self, datos_y):
        dt = 0.0001 # Intervalo de muestreo.
        t_actual = time.time()
        t0 = t_actual - len(datos_y) * dt
        eje_x = np.linspace(t0, t0 + (len(datos_y) - 1) * dt, len(datos_y))
        return eje_x, datos_y
    
    def detener(self):
        self._activo = False

class VentanaPrincipal(QMainWindow):
    def __init__(self):

        inicio = time.time()
        super().__init__()

        self.hilo_serial = None
        self.serial_port = None
        self.conectado = False
        self.boton_estado = False
        self.cola_datos = Queue()

        # Métodos de la sub-clase.
        self.setWindowTitle("Comunicación Silicon.")
        self.setGeometry(200, 200, 600, 600)

        self.crear_widgets()
        self.instanciar_hilos()
        self.conectar_senales()

        # Variables para gráfico.
        self.inicio_tiempo = time.time()  # Para el cálculo de t0.

        if self.boton_estado:
            self.configurar_puerto()

        final = time.time()
        print(f"El tiempo del método constructor fue {final - inicio} segundos.")
    
    def crear_widgets(self):
        
        inicio = time.time()

        # Etiqueta de combo box.
        self.combo_box_label = QLabel("Puertos COM",self)
        self.combo_box_label.move(10, 5)

        #Combo box.
        self.combo_box = ComboBoxDinamico(self)
        self.combo_box.setGeometry(10, 40, 200, 30)

        # Botón para iniciar conexión.
        self.boton_start_sesion = QPushButton("Iniciar sesión", self)
        self.boton_start_sesion.setGeometry(10, 80, 200, 30)

        #Indicador de estado de puerto.
        self.estatus = QLabel("No conectado", self)
        self.estatus.move(10, 100)

        # Gráfica de datos en tiempo real.
        self.grafica = pg.PlotWidget(self)
        self.curva = self.grafica.plot([], [], pen='g')  # Inicializa la curva vacía
        self.grafica.resize(350, 200)
        self.grafica.move(10, 200)
        
        # Etiqueta de matriz de entradas digitales.
        self.matriz_label = QLabel("Entradas digitales", self)
        self.matriz_label.move(380, 10)

        #Matriz de bits eficiente.
        self.matriz_2 = MatrizRapida(self, 20, 8, 20)
        self.matriz_2.move(380, 40)
        self.matriz_2.setFixedSize(self.matriz_2.tam_celda * self.matriz_2.columnas, self.matriz_2.tam_celda * self.matriz_2.filas)

        final = time.time()
        print(f"La creación de Widgets duró {final - inicio} segundos")

    def conectar_senales(self):
        self.boton_start_sesion.clicked.connect(self.abrir_o_cerrar)
        self.hilo_matriz_bits.senal_matriz_bits.connect(self.matriz_2.actualizar)
        # self.hilo_grafico.senal_grafica.connect()

        
    def abrir_o_cerrar(self):
        if not self.conectado:
            self.configurar_puerto()
            self.boton_start_sesion.setText("Puerto en uso")
        else:
            self.cerrar_puerto()
            self.boton_start_sesion.setText("Puerto cerrado.")

    def configurar_puerto(self):
         puerto_seleccionado = self.combo_box.currentText()
         try:
             self.serial_port = Serial(
                   port = puerto_seleccionado,
                   baudrate = 6_000_000, # 6 Mega Baudios.
                   bytesize = 8,
                   parity = 'N',
                   stopbits = 1,
                   timeout = 1
              )
             if self.serial_port.is_open:
                self.conectado = True
                self.estatus.setText ("Conectado")

                # Iniciar hilo de lectura de datos serial.
                self.hilo_serial = HiloSerial(self.serial_port, self.cola_datos)
                self.hilo_serial.start()
                
                
             else:
                self.estatus.setText("No se pudo abrir el puerto")
                
         except Exception as e:
             self.estatus.setText(f"Error: {e}")
             print(f"Error: {e}")

    def cerrar_puerto(self):
        # Detener el hilo si es que existe.
        if hasattr(self, "hilo_serial") and self.hilo_serial is not None:
            self.hilo_serial.detener()
            self.hilo_serial.wait()  # Espera a que el hilo termine
            self.hilo_serial = None # Se limpia esa variable/instancia.
        
        # Cerrar puerto serial si está abierto.
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.conectado = False
            self.serial_port = None
            self.estatus.setText("Desconectado.")

    def enviar_comando_at(self):
        self.serial_port.write(b'AT\n')

    def mostrar_dato_recibido(self, datos):
        print(f"Dato recibido en GUI, {datos}")

    def actualizar_grafica(self, paquete: tuple[np.ndarray, np.ndarray]):
        eje_x, datos = paquete
        self.curva.setData(eje_x, datos) # setData actualiza la curva existente con los parámetros que se indiquen.

    def instanciar_hilos(self):
        # Instanciar hilos de procesos paralelos a ventana.
        self.hilo_procesamiento = HiloProcesamiento(self.cola_datos)
        self.hilo_matriz_bits = HiloMatrizBits()
        self.hilo_grafico = HiloGrafica()
        
        # Conectar señales entre hilos.
        self.hilo_procesamiento.senal_procesada.connect(self.hilo_matriz_bits.recibir_dato)
        self.hilo_procesamiento.senal_procesada.connect(self.hilo_grafico.recibir_dato)
        self.hilo_grafico.senal_grafica.connect(self.actualizar_grafica)

        # Iniciar ejecución de hilos.
        self.hilo_procesamiento.start()
        self.hilo_matriz_bits.start()
        self.hilo_grafico.start()
        ...
    
    def closeEvent(self, event):
        # Si existe el hilo serial, detenerlo y esperar a que termine
        # La función hasattr verifica si un objeto tiene el atributo indicado.
        if hasattr(self, "hilo_serial") and self.hilo_serial is not None:
            self.hilo_serial.detener()
            self.hilo_serial.wait()  # Espera a que el hilo termine
            self.hilo_serial = None
    
        # Si el puerto serial está abierto, cerrarlo
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None

        event.accept()  # Aceptar el cierre de la ventana

inicio = time.time()

app = QApplication(sys.argv)
ventana = VentanaPrincipal()
ventana.show()

final = time.time()
print(f"Tiempo total hasta ventana.show fue de {final - inicio} segundos.")

sys.exit(app.exec())