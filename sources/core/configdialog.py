"""Configuration dialog of the COHIWizard

Rarely used settings (STEMLAB IP address, startup tab, recording path, logfile,
spectrum monitor, test mode) live in a window of their own which looks the same
for all skins. The layout is core/ressources/config_dialog.ui, generated with
    pyuic5 -x core/ressources/config_dialog.ui -o core/config_dialog.py
(call from sources/).

A skin which does not contain these widgets gets the ones of the dialog under
the same names (attach_to), so that the player and core modules access them via
gui.<name> as before. A skin which still contains them keeps its own widgets;
the corresponding dialog widgets are then hidden.
"""
from PyQt5 import QtWidgets
from core.config_dialog import Ui_ConfigDialog

# widgets that may be moved from the skins into the dialog
CONFIG_WIDGETS = (
    "pushButton_IP",
    "lineEdit_IPAddress",
    "playrec_label_startuptab",
    "playrec_comboBox_startuptab",
    "playrec_pushButton_recordingpath",
    "playrec_lineEdit_recordingpath",
    "playrec_radioButtonpushButton_write_logfile",
    "core_checkBox_show_spectrum",
    "checkBox_TESTMODE",
)


class ConfigDialog(QtWidgets.QDialog):
    """non-modal dialog, opened by the button pushButton_configuration of the skin"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ConfigDialog()
        self.ui.setupUi(self)
        self.ui.buttonBox_cfg.rejected.connect(self.close)
        self.attached = []

    def attach_to(self, gui):
        """give gui the dialog widgets which the skin does not have itself
        :param gui: Ui_MainWindow instance of the skin (after setupUi)
        :return: list of the attached widget names"""
        for name in CONFIG_WIDGETS:
            widget = getattr(self.ui, name)
            if hasattr(gui, name):
                widget.setVisible(False)      # the skin has its own one
            else:
                setattr(gui, name, widget)
                self.attached.append(name)
        for group in (self.ui.groupBox_cfg_stemlab, self.ui.groupBox_cfg_general, self.ui.groupBox_cfg_test):
            group.setVisible(any(getattr(self.ui, n).parent() is group and n in self.attached
                                 for n in CONFIG_WIDGETS))
        if hasattr(gui, "pushButton_configuration"):
            gui.pushButton_configuration.clicked.connect(self.show_dialog)
        return self.attached

    def show_dialog(self):
        self.show()
        self.raise_()
        self.activateWindow()
