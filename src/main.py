import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QComboBox, QLabel, QPushButton
from PyQt6.QtCore import QThread, pyqtSignal
from serial import Serial
import serial.tools.list_ports
import time

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

class HiloSerial(QThread):
    datos_recibidos = pyqtSignal(str) # Señal para enviar los datos crudos.

    def __init__(self, puerto_serial):
        super().__init__()
        self.serial_port = puerto_serial
        self.lectura_activa = True

    def run(self):
        # Enviar comando AT + esperar 200 ms
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.write(b'AT\n')
            time.sleep(0.2)

        while self.lectura_activa:
            if self.serial_port.in_waiting > 100:
                try:
                    # Datos en crudo del buffer serial.
                    datos = self.serial_port.read(self.serial_port.in_waiting)
                    self.datos_recibidos.emit(datos)
                except Exception as e:
                    print(f"Error de comunicación: {e}")
                    self.lectura_activa = False
            time.sleep(0.1) # Delay de 100 mseg. para no saturar el CPU.

    def detener(self):
        self.lectura_activa = False

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self.hilo_serial = None
        self.serial_port = None
        self.conectado = False
        self.boton_estado = False

        # Métodos de la sub-clase.
        self.setWindowTitle("Comunicación Silicon.")
        self.setGeometry(200, 200, 400, 300)

        self.crear_widgets()
        self.conectar_senales()

        if self.boton_estado:
            self.configurar_puerto()
    
    def crear_widgets(self):
        
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

    def conectar_senales(self):
        self.boton_start_sesion.clicked.connect(self.abrir_o_cerrar)
        
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
                   baudrate = 9600,
                   bytesize = 8,
                   parity = 'N',
                   stopbits = 1,
                   timeout = 1
              )
             if self.serial_port.is_open:
                self.conectado = True
                self.estatus.setText ("Conectado")

                # Iniciar hilo de lectura de datos serial.
                self.hilo_serial = HiloSerial(self.serial_port)
                self.hilo_serial.datos_recibidos.connect(self.mostrar_dato_recibido) # Cuando se emita una señal se llamará a la función mostrar_dato_recibido.
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
    
app = QApplication(sys.argv)
ventana = VentanaPrincipal()
ventana.show()

sys.exit(app.exec())