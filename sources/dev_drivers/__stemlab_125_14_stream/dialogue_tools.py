
#import os
#import system_module as wsys
#from SDR_wavheadertools_v2 import WAVheader_tools

from PyQt5.QtWidgets import *
#from PyQt5.QtCore import QObject, pyqtSignal, Qt
#from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg,  NavigationToolbar2QT as NavigationToolbar
#from matplotlib.figure import Figure


class TextInputDialog(QDialog):
    """A dialog for entering text input with multiple fields."""

    def __init__(self, parent=None, *args, **kwargs):
        super(TextInputDialog, self).__init__(parent)

        self.setWindowTitle("Input dialogue")
        if len(args) > 0:
            self.inputfields = args[0]

        layout = QVBoxLayout()

        # Eingabefelder
        for key, value in self.inputfields.items():
            setattr(self, f'line_edit_{key}', QLineEdit(self))
            getattr(self, f'line_edit_{key}').setText(str(value))
            layout.addWidget(QLabel(f"{key}:"))
            layout.addWidget(getattr(self, f'line_edit_{key}'))
        # self.line_edit1 = QLineEdit(self)
        # self.line_edit2 = QLineEdit(self)

        # Buttons
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)

        # Layouts
#        layout.addWidget(QLabel("carier freqency:"))
#        layout.addWidget(self.line_edit1)

 #       layout.addWidget(QLabel("Eingabe 2:"))
 #       layout.addWidget(self.line_edit2)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Signals
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)


    def getInputs(self):

        """Returns the text from the input fields."""
        # return self.line_edit1.text(), self.line_edit2.text()
        for key in self.inputfields.keys():
            line_edit = getattr(self, f'line_edit_{key}', None)
            if line_edit:
                self.inputfields[key] = line_edit.text()
        return self.inputfields