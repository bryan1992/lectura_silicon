import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QComboBox, QLabel, QPushButton
from serial import Serial
import serial.tools.list_ports

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

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

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
                
             else:
                self.estatus.setText("No se pudo abrir el puerto")
                
         except Exception as e:
             self.estatus.setText(f"Error: {e}")
             print(f"Error: {e}")

    def cerrar_puerto(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.conectado = False
            self.estatus.setText("Desconectado.")
    
app = QApplication(sys.argv)
ventana = VentanaPrincipal()
ventana.show()

sys.exit(app.exec())