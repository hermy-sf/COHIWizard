# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'wavheader_editor_widget.ui'
#
# Created by: PyQt5 UI code generator 5.15.10
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_wavheader_editor_widget(object):
    def setupUi(self, wavheader_editor_widget):
        wavheader_editor_widget.setObjectName("wavheader_editor_widget")
        wavheader_editor_widget.resize(993, 689)
        self.gridLayout_2 = QtWidgets.QGridLayout(wavheader_editor_widget)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.label_8 = QtWidgets.QLabel(wavheader_editor_widget)
        self.label_8.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_8.sizePolicy().hasHeightForWidth())
        self.label_8.setSizePolicy(sizePolicy)
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(251, 255, 203))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.NoRole, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.ToolTipBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(251, 255, 203))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.NoRole, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.ToolTipBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.NoRole, brush)
        brush = QtGui.QBrush(QtGui.QColor(234, 234, 234))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.ToolTipBase, brush)
        self.label_8.setPalette(palette)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_8.setFont(font)
        self.label_8.setAutoFillBackground(True)
        self.label_8.setStyleSheet("")
        self.label_8.setFrameShape(QtWidgets.QFrame.Panel)
        self.label_8.setObjectName("label_8")
        self.gridLayout.addWidget(self.label_8, 9, 1, 1, 1)
        self.pushButton_subtract = QtWidgets.QPushButton(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_subtract.sizePolicy().hasHeightForWidth())
        self.pushButton_subtract.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.pushButton_subtract.setFont(font)
        self.pushButton_subtract.setObjectName("pushButton_subtract")
        self.gridLayout.addWidget(self.pushButton_subtract, 4, 3, 1, 1)
        self.wavheader_dateTimeEdit_starttime = QtWidgets.QDateTimeEdit(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.wavheader_dateTimeEdit_starttime.sizePolicy().hasHeightForWidth())
        self.wavheader_dateTimeEdit_starttime.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.wavheader_dateTimeEdit_starttime.setFont(font)
        self.wavheader_dateTimeEdit_starttime.setObjectName("wavheader_dateTimeEdit_starttime")
        self.gridLayout.addWidget(self.wavheader_dateTimeEdit_starttime, 3, 2, 1, 2)
        self.wavheader_timeEdit_subtr = QtWidgets.QTimeEdit(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.wavheader_timeEdit_subtr.sizePolicy().hasHeightForWidth())
        self.wavheader_timeEdit_subtr.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.wavheader_timeEdit_subtr.setFont(font)
        self.wavheader_timeEdit_subtr.setObjectName("wavheader_timeEdit_subtr")
        self.gridLayout.addWidget(self.wavheader_timeEdit_subtr, 5, 2, 1, 2)
        self.wavheader_dateTimeEdit_result = QtWidgets.QDateTimeEdit(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.wavheader_dateTimeEdit_result.sizePolicy().hasHeightForWidth())
        self.wavheader_dateTimeEdit_result.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.wavheader_dateTimeEdit_result.setFont(font)
        self.wavheader_dateTimeEdit_result.setObjectName("wavheader_dateTimeEdit_result")
        self.gridLayout.addWidget(self.wavheader_dateTimeEdit_result, 6, 2, 1, 2)
        self.tableWidget_3 = QtWidgets.QTableWidget(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tableWidget_3.sizePolicy().hasHeightForWidth())
        self.tableWidget_3.setSizePolicy(sizePolicy)
        self.tableWidget_3.setMinimumSize(QtCore.QSize(400, 192))
        self.tableWidget_3.setMaximumSize(QtCore.QSize(700, 16777215))
        font = QtGui.QFont()
        font.setPointSize(11)
        self.tableWidget_3.setFont(font)
        self.tableWidget_3.setAutoFillBackground(True)
        self.tableWidget_3.setAlternatingRowColors(False)
        self.tableWidget_3.setObjectName("tableWidget_3")
        self.tableWidget_3.setColumnCount(1)
        self.tableWidget_3.setRowCount(6)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(12)
        item.setFont(font)
        self.tableWidget_3.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(12)
        item.setFont(font)
        self.tableWidget_3.setVerticalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(12)
        item.setFont(font)
        item.setBackground(QtGui.QColor(240, 240, 240))
        self.tableWidget_3.setVerticalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(12)
        item.setFont(font)
        self.tableWidget_3.setVerticalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(11)
        item.setFont(font)
        self.tableWidget_3.setVerticalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(11)
        item.setFont(font)
        self.tableWidget_3.setVerticalHeaderItem(5, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setPointSize(12)
        item.setFont(font)
        item.setBackground(QtGui.QColor(240, 0, 0))
        self.tableWidget_3.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        brush = QtGui.QBrush(QtGui.QColor(240, 240, 240, 240))
        brush.setStyle(QtCore.Qt.NoBrush)
        item.setForeground(brush)
        self.tableWidget_3.setItem(0, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_3.setItem(1, 0, item)
        item = QtWidgets.QTableWidgetItem()
        brush = QtGui.QBrush(QtGui.QColor(240, 240, 240, 240))
        brush.setStyle(QtCore.Qt.NoBrush)
        item.setBackground(brush)
        self.tableWidget_3.setItem(2, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_3.setItem(3, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_3.setItem(4, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_3.setItem(5, 0, item)
        self.tableWidget_3.horizontalHeader().setVisible(False)
        self.tableWidget_3.horizontalHeader().setDefaultSectionSize(600)
        self.tableWidget_3.horizontalHeader().setMinimumSectionSize(50)
        self.tableWidget_3.verticalHeader().setCascadingSectionResizes(False)
        self.tableWidget_3.verticalHeader().setDefaultSectionSize(37)
        self.tableWidget_3.verticalHeader().setSortIndicatorShown(False)
        self.tableWidget_3.verticalHeader().setStretchLastSection(False)
        self.gridLayout.addWidget(self.tableWidget_3, 8, 1, 1, 1)
        self.tableWidget_basisfields = QtWidgets.QTableWidget(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tableWidget_basisfields.sizePolicy().hasHeightForWidth())
        self.tableWidget_basisfields.setSizePolicy(sizePolicy)
        self.tableWidget_basisfields.setMinimumSize(QtCore.QSize(200, 0))
        self.tableWidget_basisfields.setMaximumSize(QtCore.QSize(400, 16777215))
        font = QtGui.QFont()
        font.setPointSize(11)
        self.tableWidget_basisfields.setFont(font)
        self.tableWidget_basisfields.setObjectName("tableWidget_basisfields")
        self.tableWidget_basisfields.setColumnCount(1)
        self.tableWidget_basisfields.setRowCount(14)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(5, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(6, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(7, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(8, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(9, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(10, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(11, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(12, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setVerticalHeaderItem(13, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(0, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(1, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(2, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(3, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(4, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(5, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(6, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(7, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(8, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(9, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(10, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(11, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(12, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_basisfields.setItem(13, 0, item)
        self.tableWidget_basisfields.horizontalHeader().setVisible(False)
        self.tableWidget_basisfields.horizontalHeader().setDefaultSectionSize(400)
        self.tableWidget_basisfields.verticalHeader().setVisible(False)
        self.gridLayout.addWidget(self.tableWidget_basisfields, 0, 0, 9, 1)
        self.pushButton_InsertHeader = QtWidgets.QPushButton(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_InsertHeader.sizePolicy().hasHeightForWidth())
        self.pushButton_InsertHeader.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.pushButton_InsertHeader.setFont(font)
        self.pushButton_InsertHeader.setObjectName("pushButton_InsertHeader")
        self.gridLayout.addWidget(self.pushButton_InsertHeader, 9, 2, 1, 1)
        self.pushButton_add = QtWidgets.QPushButton(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_add.sizePolicy().hasHeightForWidth())
        self.pushButton_add.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.pushButton_add.setFont(font)
        self.pushButton_add.setObjectName("pushButton_add")
        self.gridLayout.addWidget(self.pushButton_add, 4, 2, 1, 1)
        self.tableWidget_starttime = QtWidgets.QTableWidget(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tableWidget_starttime.sizePolicy().hasHeightForWidth())
        self.tableWidget_starttime.setSizePolicy(sizePolicy)
        self.tableWidget_starttime.setMinimumSize(QtCore.QSize(300, 380))
        self.tableWidget_starttime.setMaximumSize(QtCore.QSize(700, 16777215))
        font = QtGui.QFont()
        font.setPointSize(11)
        self.tableWidget_starttime.setFont(font)
        self.tableWidget_starttime.setObjectName("tableWidget_starttime")
        self.tableWidget_starttime.setColumnCount(2)
        self.tableWidget_starttime.setRowCount(8)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(5, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(6, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setVerticalHeaderItem(7, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(0, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(0, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(1, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(1, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(2, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(2, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(3, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(3, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(4, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(4, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(5, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(5, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(6, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(6, 1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(7, 0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget_starttime.setItem(7, 1, item)
        self.tableWidget_starttime.horizontalHeader().setDefaultSectionSize(100)
        self.gridLayout.addWidget(self.tableWidget_starttime, 0, 1, 8, 1)
        self.label_Filename_WAVHeader = QtWidgets.QLabel(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_Filename_WAVHeader.sizePolicy().hasHeightForWidth())
        self.label_Filename_WAVHeader.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.label_Filename_WAVHeader.setFont(font)
        self.label_Filename_WAVHeader.setText("")
        self.label_Filename_WAVHeader.setObjectName("label_Filename_WAVHeader")
        self.gridLayout.addWidget(self.label_Filename_WAVHeader, 10, 0, 1, 2)
        self.label_13 = QtWidgets.QLabel(wavheader_editor_widget)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.label_13.setFont(font)
        self.label_13.setObjectName("label_13")
        self.gridLayout.addWidget(self.label_13, 9, 0, 1, 1)
        self.radioButton_WAVEDIT = QtWidgets.QRadioButton(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.radioButton_WAVEDIT.sizePolicy().hasHeightForWidth())
        self.radioButton_WAVEDIT.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.radioButton_WAVEDIT.setFont(font)
        self.radioButton_WAVEDIT.setAutoFillBackground(True)
        self.radioButton_WAVEDIT.setObjectName("radioButton_WAVEDIT")
        self.gridLayout.addWidget(self.radioButton_WAVEDIT, 0, 2, 1, 1)
        self.label_9 = QtWidgets.QLabel(wavheader_editor_widget)
        self.label_9.setText("")
        self.label_9.setObjectName("label_9")
        self.gridLayout.addWidget(self.label_9, 1, 2, 1, 2)
        self.label_39 = QtWidgets.QLabel(wavheader_editor_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_39.sizePolicy().hasHeightForWidth())
        self.label_39.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_39.setFont(font)
        self.label_39.setObjectName("label_39")
        self.gridLayout.addWidget(self.label_39, 2, 2, 1, 2)
        self.gridLayout_2.addLayout(self.gridLayout, 0, 0, 1, 1)

        self.retranslateUi(wavheader_editor_widget)
        QtCore.QMetaObject.connectSlotsByName(wavheader_editor_widget)

    def retranslateUi(self, wavheader_editor_widget):
        _translate = QtCore.QCoreApplication.translate
        wavheader_editor_widget.setWindowTitle(_translate("wavheader_editor_widget", "Form"))
        self.label_8.setText(_translate("wavheader_editor_widget", "Convert dat -> wav \n"
"by inserting current wav header"))
        self.pushButton_subtract.setText(_translate("wavheader_editor_widget", "-"))
        self.wavheader_dateTimeEdit_starttime.setDisplayFormat(_translate("wavheader_editor_widget", "dd.MM.yyyy HH:mm:ss"))
        self.wavheader_timeEdit_subtr.setDisplayFormat(_translate("wavheader_editor_widget", "HH:mm:ss"))
        self.wavheader_dateTimeEdit_result.setDisplayFormat(_translate("wavheader_editor_widget", "dd.MM.yyyy HH:mm:ss"))
        self.tableWidget_3.setToolTip(_translate("wavheader_editor_widget", "make this table editable by clicking \'edit\'"))
        item = self.tableWidget_3.verticalHeaderItem(0)
        item.setText(_translate("wavheader_editor_widget", "nextfilename"))
        item = self.tableWidget_3.verticalHeaderItem(1)
        item.setText(_translate("wavheader_editor_widget", "SDR Type"))
        item = self.tableWidget_3.verticalHeaderItem(2)
        item.setText(_translate("wavheader_editor_widget", "Start"))
        item = self.tableWidget_3.verticalHeaderItem(3)
        item.setText(_translate("wavheader_editor_widget", "dataheader"))
        item = self.tableWidget_3.verticalHeaderItem(4)
        item.setText(_translate("wavheader_editor_widget", "duration header (s)"))
        item = self.tableWidget_3.verticalHeaderItem(5)
        item.setText(_translate("wavheader_editor_widget", "duration bytes (s)"))
        item = self.tableWidget_3.horizontalHeaderItem(0)
        item.setText(_translate("wavheader_editor_widget", "value"))
        __sortingEnabled = self.tableWidget_3.isSortingEnabled()
        self.tableWidget_3.setSortingEnabled(False)
        item = self.tableWidget_3.item(0, 0)
        item.setText(_translate("wavheader_editor_widget", "-"))
        item = self.tableWidget_3.item(1, 0)
        item.setText(_translate("wavheader_editor_widget", "-"))
        item = self.tableWidget_3.item(2, 0)
        item.setText(_translate("wavheader_editor_widget", "-"))
        item = self.tableWidget_3.item(3, 0)
        item.setText(_translate("wavheader_editor_widget", "-"))
        item = self.tableWidget_3.item(4, 0)
        item.setText(_translate("wavheader_editor_widget", "-"))
        item = self.tableWidget_3.item(5, 0)
        item.setText(_translate("wavheader_editor_widget", "-"))
        self.tableWidget_3.setSortingEnabled(__sortingEnabled)
        self.tableWidget_basisfields.setToolTip(_translate("wavheader_editor_widget", "make this table editable by clicking \'edit\'"))
        item = self.tableWidget_basisfields.verticalHeaderItem(0)
        item.setText(_translate("wavheader_editor_widget", "Filesize"))
        item = self.tableWidget_basisfields.verticalHeaderItem(1)
        item.setText(_translate("wavheader_editor_widget", "sdr_nChunksize"))
        item = self.tableWidget_basisfields.verticalHeaderItem(2)
        item.setText(_translate("wavheader_editor_widget", "wFormatTag"))
        item = self.tableWidget_basisfields.verticalHeaderItem(3)
        item.setText(_translate("wavheader_editor_widget", "nChannels"))
        item = self.tableWidget_basisfields.verticalHeaderItem(4)
        item.setText(_translate("wavheader_editor_widget", "Sample rate"))
        item = self.tableWidget_basisfields.verticalHeaderItem(5)
        item.setText(_translate("wavheader_editor_widget", "bytes per second"))
        item = self.tableWidget_basisfields.verticalHeaderItem(6)
        item.setText(_translate("wavheader_editor_widget", "nBlockalign"))
        item = self.tableWidget_basisfields.verticalHeaderItem(7)
        item.setText(_translate("wavheader_editor_widget", "bits per sample"))
        item = self.tableWidget_basisfields.verticalHeaderItem(8)
        item.setText(_translate("wavheader_editor_widget", "centerfreq"))
        item = self.tableWidget_basisfields.verticalHeaderItem(9)
        item.setText(_translate("wavheader_editor_widget", "dataChunksize"))
        item = self.tableWidget_basisfields.verticalHeaderItem(10)
        item.setText(_translate("wavheader_editor_widget", "ADFrequency"))
        item = self.tableWidget_basisfields.verticalHeaderItem(11)
        item.setText(_translate("wavheader_editor_widget", "IFFrequency"))
        item = self.tableWidget_basisfields.verticalHeaderItem(12)
        item.setText(_translate("wavheader_editor_widget", "Bandwidth"))
        item = self.tableWidget_basisfields.verticalHeaderItem(13)
        item.setText(_translate("wavheader_editor_widget", "IQOffset"))
        item = self.tableWidget_basisfields.horizontalHeaderItem(0)
        item.setText(_translate("wavheader_editor_widget", "value"))
        __sortingEnabled = self.tableWidget_basisfields.isSortingEnabled()
        self.tableWidget_basisfields.setSortingEnabled(False)
        item = self.tableWidget_basisfields.item(0, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(1, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(2, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(3, 0)
        item.setText(_translate("wavheader_editor_widget", "2"))
        item = self.tableWidget_basisfields.item(4, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(5, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(6, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(7, 0)
        item.setText(_translate("wavheader_editor_widget", "16"))
        item = self.tableWidget_basisfields.item(8, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(9, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(10, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(11, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(12, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_basisfields.item(13, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        self.tableWidget_basisfields.setSortingEnabled(__sortingEnabled)
        self.pushButton_InsertHeader.setToolTip(_translate("wavheader_editor_widget", "insert header into dat file"))
        self.pushButton_InsertHeader.setText(_translate("wavheader_editor_widget", "Insert \n"
"Header"))
        self.pushButton_add.setText(_translate("wavheader_editor_widget", "+"))
        self.tableWidget_starttime.setToolTip(_translate("wavheader_editor_widget", "make this table editable by clicking \'edit\'"))
        item = self.tableWidget_starttime.verticalHeaderItem(0)
        item.setText(_translate("wavheader_editor_widget", "YYYY"))
        item = self.tableWidget_starttime.verticalHeaderItem(1)
        item.setText(_translate("wavheader_editor_widget", "MM"))
        item = self.tableWidget_starttime.verticalHeaderItem(2)
        item.setText(_translate("wavheader_editor_widget", "---"))
        item = self.tableWidget_starttime.verticalHeaderItem(3)
        item.setText(_translate("wavheader_editor_widget", "DD"))
        item = self.tableWidget_starttime.verticalHeaderItem(4)
        item.setText(_translate("wavheader_editor_widget", "HH"))
        item = self.tableWidget_starttime.verticalHeaderItem(5)
        item.setText(_translate("wavheader_editor_widget", "mm"))
        item = self.tableWidget_starttime.verticalHeaderItem(6)
        item.setText(_translate("wavheader_editor_widget", "ss"))
        item = self.tableWidget_starttime.verticalHeaderItem(7)
        item.setText(_translate("wavheader_editor_widget", "ms"))
        item = self.tableWidget_starttime.horizontalHeaderItem(0)
        item.setText(_translate("wavheader_editor_widget", "Start"))
        item = self.tableWidget_starttime.horizontalHeaderItem(1)
        item.setText(_translate("wavheader_editor_widget", "Stop"))
        __sortingEnabled = self.tableWidget_starttime.isSortingEnabled()
        self.tableWidget_starttime.setSortingEnabled(False)
        item = self.tableWidget_starttime.item(0, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(0, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(1, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(1, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(2, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(2, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(3, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(3, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(4, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(4, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(5, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(5, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(6, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(6, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(7, 0)
        item.setText(_translate("wavheader_editor_widget", "0"))
        item = self.tableWidget_starttime.item(7, 1)
        item.setText(_translate("wavheader_editor_widget", "0"))
        self.tableWidget_starttime.setSortingEnabled(__sortingEnabled)
        self.label_13.setText(_translate("wavheader_editor_widget", "Filename:"))
        self.radioButton_WAVEDIT.setToolTip(_translate("wavheader_editor_widget", "make this table editable by clicking \'edit\'"))
        self.radioButton_WAVEDIT.setText(_translate("wavheader_editor_widget", "EDIT"))
        self.label_39.setText(_translate("wavheader_editor_widget", "Aux time calculator"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    wavheader_editor_widget = QtWidgets.QWidget()
    ui = Ui_wavheader_editor_widget()
    ui.setupUi(wavheader_editor_widget)
    wavheader_editor_widget.show()
    sys.exit(app.exec_())
