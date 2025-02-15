# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '.\annotator_widget.ui'
#
# Created by: PyQt5 UI code generator 5.15.10
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_annotator_widget(object):
    def setupUi(self, annotator_widget):
        annotator_widget.setObjectName("annotator_widget")
        annotator_widget.resize(1212, 888)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(annotator_widget.sizePolicy().hasHeightForWidth())
        annotator_widget.setSizePolicy(sizePolicy)
        self.gridLayout = QtWidgets.QGridLayout(annotator_widget)
        self.gridLayout.setObjectName("gridLayout")
        self.gridLayout_3 = QtWidgets.QGridLayout()
        self.gridLayout_3.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.label_18 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_18.sizePolicy().hasHeightForWidth())
        self.label_18.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_18.setFont(font)
        self.label_18.setObjectName("label_18")
        self.gridLayout_3.addWidget(self.label_18, 5, 3, 1, 1)
        self.label = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.gridLayout_3.addWidget(self.label, 11, 0, 1, 8)
        self.Annotate_listWidget = QtWidgets.QListWidget(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Annotate_listWidget.sizePolicy().hasHeightForWidth())
        self.Annotate_listWidget.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.Annotate_listWidget.setFont(font)
        self.Annotate_listWidget.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.Annotate_listWidget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.Annotate_listWidget.setAlternatingRowColors(True)
        self.Annotate_listWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.Annotate_listWidget.setMovement(QtWidgets.QListView.Free)
        self.Annotate_listWidget.setObjectName("Annotate_listWidget")
        item = QtWidgets.QListWidgetItem()
        brush = QtGui.QBrush(QtGui.QColor(170, 255, 127))
        brush.setStyle(QtCore.Qt.Dense3Pattern)
        item.setBackground(brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 50))
        brush.setStyle(QtCore.Qt.NoBrush)
        item.setForeground(brush)
        self.Annotate_listWidget.addItem(item)
        item = QtWidgets.QListWidgetItem()
        self.Annotate_listWidget.addItem(item)
        self.gridLayout_3.addWidget(self.Annotate_listWidget, 10, 0, 1, 8)
        self.label_Filename_Annotate = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_Filename_Annotate.sizePolicy().hasHeightForWidth())
        self.label_Filename_Annotate.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_Filename_Annotate.setFont(font)
        self.label_Filename_Annotate.setText("")
        self.label_Filename_Annotate.setObjectName("label_Filename_Annotate")
        self.gridLayout_3.addWidget(self.label_Filename_Annotate, 13, 1, 1, 7)
        self.label_6 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_6.sizePolicy().hasHeightForWidth())
        self.label_6.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_6.setFont(font)
        self.label_6.setObjectName("label_6")
        self.gridLayout_3.addWidget(self.label_6, 3, 0, 1, 1)
        self.radioButton_plotpreview = QtWidgets.QRadioButton(annotator_widget)
        self.radioButton_plotpreview.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.radioButton_plotpreview.sizePolicy().hasHeightForWidth())
        self.radioButton_plotpreview.setSizePolicy(sizePolicy)
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.AlternateBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(240, 240, 240))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(227, 227, 227))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(246, 246, 246))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.AlternateBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.AlternateBase, brush)
        self.radioButton_plotpreview.setPalette(palette)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.radioButton_plotpreview.setFont(font)
        self.radioButton_plotpreview.setObjectName("radioButton_plotpreview")
        self.gridLayout_3.addWidget(self.radioButton_plotpreview, 12, 7, 1, 1)
        self.progressBar_2 = QtWidgets.QProgressBar(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar_2.sizePolicy().hasHeightForWidth())
        self.progressBar_2.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.progressBar_2.setFont(font)
        self.progressBar_2.setProperty("value", 24)
        self.progressBar_2.setObjectName("progressBar_2")
        self.gridLayout_3.addWidget(self.progressBar_2, 12, 0, 1, 7)
        self.label_11 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_11.sizePolicy().hasHeightForWidth())
        self.label_11.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_11.setFont(font)
        self.label_11.setObjectName("label_11")
        self.gridLayout_3.addWidget(self.label_11, 13, 0, 1, 1)
        self.label_17 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_17.sizePolicy().hasHeightForWidth())
        self.label_17.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_17.setFont(font)
        self.label_17.setObjectName("label_17")
        self.gridLayout_3.addWidget(self.label_17, 6, 0, 1, 1)
        self.label_16 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_16.sizePolicy().hasHeightForWidth())
        self.label_16.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_16.setFont(font)
        self.label_16.setObjectName("label_16")
        self.gridLayout_3.addWidget(self.label_16, 5, 0, 1, 1)
        self.lineEdit = QtWidgets.QLineEdit(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit.sizePolicy().hasHeightForWidth())
        self.lineEdit.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit.setFont(font)
        self.lineEdit.setText("")
        self.lineEdit.setObjectName("lineEdit")
        self.gridLayout_3.addWidget(self.lineEdit, 6, 1, 1, 6)
        self.lineEdit_Country = QtWidgets.QLineEdit(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_Country.sizePolicy().hasHeightForWidth())
        self.lineEdit_Country.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_Country.setFont(font)
        self.lineEdit_Country.setText("")
        self.lineEdit_Country.setObjectName("lineEdit_Country")
        self.gridLayout_3.addWidget(self.lineEdit_Country, 5, 1, 1, 2)
        self.labelFrequency = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.labelFrequency.sizePolicy().hasHeightForWidth())
        self.labelFrequency.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.labelFrequency.setFont(font)
        self.labelFrequency.setObjectName("labelFrequency")
        self.gridLayout_3.addWidget(self.labelFrequency, 4, 0, 1, 1)
        self.lineEdit_TX_Site = QtWidgets.QLineEdit(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_TX_Site.sizePolicy().hasHeightForWidth())
        self.lineEdit_TX_Site.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_TX_Site.setFont(font)
        self.lineEdit_TX_Site.setText("")
        self.lineEdit_TX_Site.setObjectName("lineEdit_TX_Site")
        self.gridLayout_3.addWidget(self.lineEdit_TX_Site, 5, 4, 1, 3)
        self.pushButtonAnnotate = QtWidgets.QPushButton(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButtonAnnotate.sizePolicy().hasHeightForWidth())
        self.pushButtonAnnotate.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButtonAnnotate.setFont(font)
        self.pushButtonAnnotate.setObjectName("pushButtonAnnotate")
        self.gridLayout_3.addWidget(self.pushButtonAnnotate, 3, 7, 1, 1)
        self.pushButton_Scan = QtWidgets.QPushButton(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButton_Scan.setFont(font)
        self.pushButton_Scan.setObjectName("pushButton_Scan")
        self.gridLayout_3.addWidget(self.pushButton_Scan, 3, 6, 1, 1)
        self.spinBoxNumScan = QtWidgets.QSpinBox(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.spinBoxNumScan.setFont(font)
        self.spinBoxNumScan.setKeyboardTracking(False)
        self.spinBoxNumScan.setMaximum(99999)
        self.spinBoxNumScan.setProperty("value", 20)
        self.spinBoxNumScan.setObjectName("spinBoxNumScan")
        self.gridLayout_3.addWidget(self.spinBoxNumScan, 3, 5, 1, 1)
        self.label_2 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_2.setFont(font)
        self.label_2.setObjectName("label_2")
        self.gridLayout_3.addWidget(self.label_2, 3, 4, 1, 1)
        self.spinBoxminSNR = QtWidgets.QSpinBox(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.spinBoxminSNR.setFont(font)
        self.spinBoxminSNR.setKeyboardTracking(False)
        self.spinBoxminSNR.setMinimum(0)
        self.spinBoxminSNR.setMaximum(100)
        self.spinBoxminSNR.setSingleStep(5)
        self.spinBoxminSNR.setProperty("value", 10)
        self.spinBoxminSNR.setObjectName("spinBoxminSNR")
        self.gridLayout_3.addWidget(self.spinBoxminSNR, 3, 3, 1, 1)
        self.label_3 = QtWidgets.QLabel(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_3.setFont(font)
        self.label_3.setObjectName("label_3")
        self.gridLayout_3.addWidget(self.label_3, 3, 2, 1, 1)
        self.pushButtonENTER = QtWidgets.QPushButton(annotator_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButtonENTER.sizePolicy().hasHeightForWidth())
        self.pushButtonENTER.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButtonENTER.setFont(font)
        self.pushButtonENTER.setObjectName("pushButtonENTER")
        self.gridLayout_3.addWidget(self.pushButtonENTER, 6, 7, 1, 1)
        self.pushButtonDiscard = QtWidgets.QPushButton(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButtonDiscard.setFont(font)
        self.pushButtonDiscard.setObjectName("pushButtonDiscard")
        self.gridLayout_3.addWidget(self.pushButtonDiscard, 5, 7, 1, 1)
        self.annotate_pushButtonBack = QtWidgets.QPushButton(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.annotate_pushButtonBack.setFont(font)
        self.annotate_pushButtonBack.setAutoFillBackground(True)
        self.annotate_pushButtonBack.setObjectName("annotate_pushButtonBack")
        self.gridLayout_3.addWidget(self.annotate_pushButtonBack, 4, 7, 1, 1)
        self.radioButton_export_xlsx = QtWidgets.QRadioButton(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.radioButton_export_xlsx.setFont(font)
        self.radioButton_export_xlsx.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.radioButton_export_xlsx.setAutoExclusive(False)
        self.radioButton_export_xlsx.setObjectName("radioButton_export_xlsx")
        self.gridLayout_3.addWidget(self.radioButton_export_xlsx, 4, 6, 1, 1)
        self.label_5 = QtWidgets.QLabel(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.gridLayout_3.addWidget(self.label_5, 4, 4, 1, 1)
        self.peakBW_comboBox = QtWidgets.QComboBox(annotator_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.peakBW_comboBox.setFont(font)
        self.peakBW_comboBox.setObjectName("peakBW_comboBox")
        self.peakBW_comboBox.addItem("")
        self.peakBW_comboBox.addItem("")
        self.peakBW_comboBox.addItem("")
        self.gridLayout_3.addWidget(self.peakBW_comboBox, 4, 5, 1, 1)
        self.gridLayout.addLayout(self.gridLayout_3, 0, 0, 1, 1)

        self.retranslateUi(annotator_widget)
        QtCore.QMetaObject.connectSlotsByName(annotator_widget)

    def retranslateUi(self, annotator_widget):
        _translate = QtCore.QCoreApplication.translate
        annotator_widget.setWindowTitle(_translate("annotator_widget", "Form"))
        self.label_18.setToolTip(_translate("annotator_widget", "TX site"))
        self.label_18.setText(_translate("annotator_widget", "TX-site"))
        self.label.setText(_translate("annotator_widget", "Status:"))
        self.Annotate_listWidget.setToolTip(_translate("annotator_widget", "space for stations list"))
        __sortingEnabled = self.Annotate_listWidget.isSortingEnabled()
        self.Annotate_listWidget.setSortingEnabled(False)
        item = self.Annotate_listWidget.item(0)
        item.setText(_translate("annotator_widget", "TESTITEM1"))
        item = self.Annotate_listWidget.item(1)
        item.setText(_translate("annotator_widget", "TESTITEM2"))
        self.Annotate_listWidget.setSortingEnabled(__sortingEnabled)
        self.label_6.setToolTip(_translate("annotator_widget", "baseline offset , adjustable in Tan \'Scanner\'"))
        self.label_6.setText(_translate("annotator_widget", "Baseline Offset: "))
        self.radioButton_plotpreview.setToolTip(_translate("annotator_widget", "allow plotting of spectra during scanning"))
        self.radioButton_plotpreview.setText(_translate("annotator_widget", "plot preview"))
        self.label_11.setText(_translate("annotator_widget", "Filename:"))
        self.label_17.setToolTip(_translate("annotator_widget", "name of the station/programme"))
        self.label_17.setText(_translate("annotator_widget", "Programme"))
        self.label_16.setToolTip(_translate("annotator_widget", "country  of found transmitter"))
        self.label_16.setText(_translate("annotator_widget", "Country:"))
        self.lineEdit.setToolTip(_translate("annotator_widget", "name of the station/programme"))
        self.lineEdit_Country.setToolTip(_translate("annotator_widget", "country  of found transmitter"))
        self.labelFrequency.setToolTip(_translate("annotator_widget", "shows frequency of current peak"))
        self.labelFrequency.setText(_translate("annotator_widget", "Freq:"))
        self.lineEdit_TX_Site.setToolTip(_translate("annotator_widget", "TX site"))
        self.pushButtonAnnotate.setToolTip(_translate("annotator_widget", "assign peaks to candidates of stations"))
        self.pushButtonAnnotate.setText(_translate("annotator_widget", "Annotate"))
        self.pushButton_Scan.setToolTip(_translate("annotator_widget", "Scan record, extract peaks with SNR > min SNR"))
        self.pushButton_Scan.setText(_translate("annotator_widget", "Scan"))
        self.spinBoxNumScan.setToolTip(_translate("annotator_widget", "number of evaluation steps when scanning record for peaks"))
        self.label_2.setToolTip(_translate("annotator_widget", "number of evaluation steps when scanning record for peaks"))
        self.label_2.setText(_translate("annotator_widget", "#scan steps"))
        self.spinBoxminSNR.setToolTip(_translate("annotator_widget", "minimum SNR for auto-selection of peaks"))
        self.label_3.setToolTip(_translate("annotator_widget", "minimum SNR for auto-selection of peaks"))
        self.label_3.setText(_translate("annotator_widget", "min SNR (dB)"))
        self.pushButtonENTER.setToolTip(_translate("annotator_widget", "Accept and transfer to annotation yaml"))
        self.pushButtonENTER.setText(_translate("annotator_widget", "ENTER"))
        self.pushButtonENTER.setShortcut(_translate("annotator_widget", "Return"))
        self.pushButtonDiscard.setToolTip(_translate("annotator_widget", "ignore current table and proceed to next frequency"))
        self.pushButtonDiscard.setText(_translate("annotator_widget", "Discard"))
        self.pushButtonDiscard.setShortcut(_translate("annotator_widget", "Alt+Right"))
        self.annotate_pushButtonBack.setToolTip(_translate("annotator_widget", "Add a station to the last frequency (e.g. interference)"))
        self.annotate_pushButtonBack.setText(_translate("annotator_widget", "Add station to last F"))
        self.annotate_pushButtonBack.setShortcut(_translate("annotator_widget", "Alt+Left"))
        self.radioButton_export_xlsx.setToolTip(_translate("annotator_widget", "Export time series of found peaks to Excel xlsx Table"))
        self.radioButton_export_xlsx.setText(_translate("annotator_widget", "Export \n"
" peaktraces"))
        self.label_5.setToolTip(_translate("annotator_widget", "listing resolution of peak frequencies; e.g. 100 Hz means that a peak at 120.1 kHz shows up at 120.1 while a peak at 120.06 kHz shows up at 120.2 (rounding to next 0.1kHz)"))
        self.label_5.setText(_translate("annotator_widget", "Peak detection\n"
"Bandwidth"))
        self.peakBW_comboBox.setToolTip(_translate("annotator_widget", "listing resolution of peak frequencies; e.g. 100 Hz means that a peak at 120.1 kHz shows up at 120.1 while a peak at 120.06 kHz shows up at 120.2 (rounding to next 0.1kHz)"))
        self.peakBW_comboBox.setItemText(0, _translate("annotator_widget", "1 kHz"))
        self.peakBW_comboBox.setItemText(1, _translate("annotator_widget", "100 Hz"))
        self.peakBW_comboBox.setItemText(2, _translate("annotator_widget", "10Hz"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    annotator_widget = QtWidgets.QWidget()
    ui = Ui_annotator_widget()
    ui.setupUi(annotator_widget)
    annotator_widget.show()
    sys.exit(app.exec_())
