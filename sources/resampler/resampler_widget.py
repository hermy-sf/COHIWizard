# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'resampler_widget.ui'
#
# Created by: PyQt5 UI code generator 5.15.11
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_resampler_widget(object):
    def setupUi(self, resampler_widget):
        resampler_widget.setObjectName("resampler_widget")
        resampler_widget.resize(1127, 704)
        font = QtGui.QFont()
        font.setPointSize(10)
        resampler_widget.setFont(font)
        self.gridLayout = QtWidgets.QGridLayout(resampler_widget)
        self.gridLayout.setObjectName("gridLayout")
        self.gridLayout_5 = QtWidgets.QGridLayout()
        self.gridLayout_5.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.lineEdit_2 = QtWidgets.QLineEdit(resampler_widget)
        self.lineEdit_2.setEnabled(False)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_2.setFont(font)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.gridLayout_5.addWidget(self.lineEdit_2, 4, 1, 1, 1)
        self.label_Filename_resample = QtWidgets.QLabel(resampler_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_Filename_resample.setFont(font)
        self.label_Filename_resample.setText("")
        self.label_Filename_resample.setObjectName("label_Filename_resample")
        self.gridLayout_5.addWidget(self.label_Filename_resample, 13, 1, 1, 4)
        self.label_36 = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_36.sizePolicy().hasHeightForWidth())
        self.label_36.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_36.setFont(font)
        self.label_36.setObjectName("label_36")
        self.gridLayout_5.addWidget(self.label_36, 14, 0, 1, 1)
        self.progressBar_resample = QtWidgets.QProgressBar(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar_resample.sizePolicy().hasHeightForWidth())
        self.progressBar_resample.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.progressBar_resample.setFont(font)
        self.progressBar_resample.setProperty("value", 0)
        self.progressBar_resample.setObjectName("progressBar_resample")
        self.gridLayout_5.addWidget(self.progressBar_resample, 14, 1, 1, 4)
        self.listWidget_sourcelist_2 = QtWidgets.QListWidget(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.listWidget_sourcelist_2.sizePolicy().hasHeightForWidth())
        self.listWidget_sourcelist_2.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.listWidget_sourcelist_2.setFont(font)
        self.listWidget_sourcelist_2.setDragEnabled(False)
        self.listWidget_sourcelist_2.setDragDropOverwriteMode(False)
        self.listWidget_sourcelist_2.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.listWidget_sourcelist_2.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.listWidget_sourcelist_2.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_sourcelist_2.setObjectName("listWidget_sourcelist_2")
        self.gridLayout_5.addWidget(self.listWidget_sourcelist_2, 10, 4, 1, 1)
        self.label_38 = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_38.sizePolicy().hasHeightForWidth())
        self.label_38.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_38.setFont(font)
        self.label_38.setObjectName("label_38")
        self.gridLayout_5.addWidget(self.label_38, 8, 5, 1, 1)
        self.label_41 = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_41.sizePolicy().hasHeightForWidth())
        self.label_41.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_41.setFont(font)
        self.label_41.setObjectName("label_41")
        self.gridLayout_5.addWidget(self.label_41, 8, 4, 1, 1)
        self.label_34 = QtWidgets.QLabel(resampler_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_34.setFont(font)
        self.label_34.setText("")
        self.label_34.setObjectName("label_34")
        self.gridLayout_5.addWidget(self.label_34, 2, 2, 1, 1)
        self.label_31 = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_31.sizePolicy().hasHeightForWidth())
        self.label_31.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_31.setFont(font)
        self.label_31.setObjectName("label_31")
        self.gridLayout_5.addWidget(self.label_31, 2, 3, 1, 1)
        self.comboBox_resample_targetSR = QtWidgets.QComboBox(resampler_widget)
        self.comboBox_resample_targetSR.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.comboBox_resample_targetSR.sizePolicy().hasHeightForWidth())
        self.comboBox_resample_targetSR.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.comboBox_resample_targetSR.setFont(font)
        self.comboBox_resample_targetSR.setEditable(False)
        self.comboBox_resample_targetSR.setObjectName("comboBox_resample_targetSR")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.comboBox_resample_targetSR.addItem("")
        self.gridLayout_5.addWidget(self.comboBox_resample_targetSR, 2, 4, 1, 1)
        self.label_30 = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_30.sizePolicy().hasHeightForWidth())
        self.label_30.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_30.setFont(font)
        self.label_30.setObjectName("label_30")
        self.gridLayout_5.addWidget(self.label_30, 13, 0, 1, 1)
        self.label_29 = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_29.sizePolicy().hasHeightForWidth())
        self.label_29.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_29.setFont(font)
        self.label_29.setObjectName("label_29")
        self.gridLayout_5.addWidget(self.label_29, 3, 3, 1, 1)
        self.lineEdit_resample_Gain = QtWidgets.QLineEdit(resampler_widget)
        self.lineEdit_resample_Gain.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_resample_Gain.sizePolicy().hasHeightForWidth())
        self.lineEdit_resample_Gain.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_resample_Gain.setFont(font)
        self.lineEdit_resample_Gain.setObjectName("lineEdit_resample_Gain")
        self.gridLayout_5.addWidget(self.lineEdit_resample_Gain, 4, 4, 1, 1)
        self.timeEdit_resample_startcut = QtWidgets.QTimeEdit(resampler_widget)
        self.timeEdit_resample_startcut.setEnabled(False)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.timeEdit_resample_startcut.setFont(font)
        self.timeEdit_resample_startcut.setObjectName("timeEdit_resample_startcut")
        self.gridLayout_5.addWidget(self.timeEdit_resample_startcut, 2, 1, 1, 1)
        self.lineEdit_resample_targetLO = QtWidgets.QLineEdit(resampler_widget)
        self.lineEdit_resample_targetLO.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_resample_targetLO.sizePolicy().hasHeightForWidth())
        self.lineEdit_resample_targetLO.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_resample_targetLO.setFont(font)
        self.lineEdit_resample_targetLO.setText("")
        self.lineEdit_resample_targetLO.setObjectName("lineEdit_resample_targetLO")
        self.gridLayout_5.addWidget(self.lineEdit_resample_targetLO, 3, 4, 1, 1)
        self.label_33 = QtWidgets.QLabel(resampler_widget)
        self.label_33.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_33.sizePolicy().hasHeightForWidth())
        self.label_33.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_33.setFont(font)
        self.label_33.setObjectName("label_33")
        self.gridLayout_5.addWidget(self.label_33, 2, 0, 1, 1)
        self.graphicsView_resample = QtWidgets.QGraphicsView(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.graphicsView_resample.sizePolicy().hasHeightForWidth())
        self.graphicsView_resample.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.graphicsView_resample.setFont(font)
        self.graphicsView_resample.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.graphicsView_resample.setObjectName("graphicsView_resample")
        self.gridLayout_5.addWidget(self.graphicsView_resample, 8, 0, 5, 4)
        self.timeEdit_resample_stopcut = QtWidgets.QTimeEdit(resampler_widget)
        self.timeEdit_resample_stopcut.setEnabled(False)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.timeEdit_resample_stopcut.setFont(font)
        self.timeEdit_resample_stopcut.setObjectName("timeEdit_resample_stopcut")
        self.gridLayout_5.addWidget(self.timeEdit_resample_stopcut, 3, 1, 1, 1)
        self.label_37 = QtWidgets.QLabel(resampler_widget)
        self.label_37.setEnabled(False)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_37.setFont(font)
        self.label_37.setObjectName("label_37")
        self.gridLayout_5.addWidget(self.label_37, 3, 0, 1, 1)
        self.label_28 = QtWidgets.QLabel(resampler_widget)
        self.label_28.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_28.sizePolicy().hasHeightForWidth())
        self.label_28.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_28.setFont(font)
        self.label_28.setObjectName("label_28")
        self.gridLayout_5.addWidget(self.label_28, 4, 0, 1, 1)
        self.radioButton_advanced_sampling = QtWidgets.QRadioButton(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.radioButton_advanced_sampling.sizePolicy().hasHeightForWidth())
        self.radioButton_advanced_sampling.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.radioButton_advanced_sampling.setFont(font)
        self.radioButton_advanced_sampling.setAutoExclusive(False)
        self.radioButton_advanced_sampling.setObjectName("radioButton_advanced_sampling")
        self.gridLayout_5.addWidget(self.radioButton_advanced_sampling, 4, 5, 1, 1)
        self.radioButton_resgain = QtWidgets.QRadioButton(resampler_widget)
        self.radioButton_resgain.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.radioButton_resgain.sizePolicy().hasHeightForWidth())
        self.radioButton_resgain.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.radioButton_resgain.setFont(font)
        self.radioButton_resgain.setAutoExclusive(False)
        self.radioButton_resgain.setObjectName("radioButton_resgain")
        self.gridLayout_5.addWidget(self.radioButton_resgain, 4, 3, 1, 1)
        self.label_resample_targetfilename = QtWidgets.QLabel(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_resample_targetfilename.sizePolicy().hasHeightForWidth())
        self.label_resample_targetfilename.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_resample_targetfilename.setFont(font)
        self.label_resample_targetfilename.setObjectName("label_resample_targetfilename")
        self.gridLayout_5.addWidget(self.label_resample_targetfilename, 5, 3, 1, 1)
        self.lineEdit_resample_targetnameprefix = QtWidgets.QLineEdit(resampler_widget)
        self.lineEdit_resample_targetnameprefix.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_resample_targetnameprefix.sizePolicy().hasHeightForWidth())
        self.lineEdit_resample_targetnameprefix.setSizePolicy(sizePolicy)
        palette = QtGui.QPalette()
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
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.NoRole, brush)
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
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.NoRole, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 254, 210))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Light, brush)
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
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.NoRole, brush)
        self.lineEdit_resample_targetnameprefix.setPalette(palette)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_resample_targetnameprefix.setFont(font)
        self.lineEdit_resample_targetnameprefix.setText("")
        self.lineEdit_resample_targetnameprefix.setObjectName("lineEdit_resample_targetnameprefix")
        self.gridLayout_5.addWidget(self.lineEdit_resample_targetnameprefix, 5, 4, 1, 2)
        self.pushButton_resample_cancel = QtWidgets.QPushButton(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_resample_cancel.sizePolicy().hasHeightForWidth())
        self.pushButton_resample_cancel.setSizePolicy(sizePolicy)
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Dark, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Shadow, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(160, 160, 160))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Dark, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Shadow, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(160, 160, 160))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Dark, brush)
        brush = QtGui.QBrush(QtGui.QColor(120, 120, 120))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(206, 206, 206))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Shadow, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, brush)
        self.pushButton_resample_cancel.setPalette(palette)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setKerning(True)
        self.pushButton_resample_cancel.setFont(font)
        self.pushButton_resample_cancel.setAutoFillBackground(True)
        self.pushButton_resample_cancel.setObjectName("pushButton_resample_cancel")
        self.gridLayout_5.addWidget(self.pushButton_resample_cancel, 2, 5, 1, 1)
        self.pushButton_resample_resample = QtWidgets.QPushButton(resampler_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButton_resample_resample.setFont(font)
        self.pushButton_resample_resample.setObjectName("pushButton_resample_resample")
        self.gridLayout_5.addWidget(self.pushButton_resample_resample, 13, 5, 1, 1)
        self.pushButton_resample_split2G = QtWidgets.QPushButton(resampler_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButton_resample_split2G.setFont(font)
        self.pushButton_resample_split2G.setObjectName("pushButton_resample_split2G")
        self.gridLayout_5.addWidget(self.pushButton_resample_split2G, 14, 5, 1, 1)
        self.checkBox_AutoMerge2G = QtWidgets.QCheckBox(resampler_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.checkBox_AutoMerge2G.setFont(font)
        self.checkBox_AutoMerge2G.setObjectName("checkBox_AutoMerge2G")
        self.gridLayout_5.addWidget(self.checkBox_AutoMerge2G, 12, 5, 1, 1)
        self.checkBox_merge_selectall = QtWidgets.QCheckBox(resampler_widget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.checkBox_merge_selectall.setFont(font)
        self.checkBox_merge_selectall.setObjectName("checkBox_merge_selectall")
        self.gridLayout_5.addWidget(self.checkBox_merge_selectall, 12, 4, 1, 1)
        self.listWidget_playlist_2 = QtWidgets.QListWidget(resampler_widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.listWidget_playlist_2.sizePolicy().hasHeightForWidth())
        self.listWidget_playlist_2.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.listWidget_playlist_2.setFont(font)
        self.listWidget_playlist_2.setDragEnabled(False)
        self.listWidget_playlist_2.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.listWidget_playlist_2.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.listWidget_playlist_2.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_playlist_2.setObjectName("listWidget_playlist_2")
        self.gridLayout_5.addWidget(self.listWidget_playlist_2, 10, 5, 2, 1)
        self.checkBox_Cut = QtWidgets.QCheckBox(resampler_widget)
        self.checkBox_Cut.setObjectName("checkBox_Cut")
        self.gridLayout_5.addWidget(self.checkBox_Cut, 5, 1, 1, 1)
        self.pushButton_resample_correctwavheaders = QtWidgets.QPushButton(resampler_widget)
        self.pushButton_resample_correctwavheaders.setObjectName("pushButton_resample_correctwavheaders")
        self.gridLayout_5.addWidget(self.pushButton_resample_correctwavheaders, 15, 5, 1, 1)
        self.pushButton_resample_GainOnly = QtWidgets.QPushButton(resampler_widget)
        self.pushButton_resample_GainOnly.setEnabled(False)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pushButton_resample_GainOnly.setFont(font)
        self.pushButton_resample_GainOnly.setObjectName("pushButton_resample_GainOnly")
        self.gridLayout_5.addWidget(self.pushButton_resample_GainOnly, 15, 4, 1, 1)
        self.gridLayout.addLayout(self.gridLayout_5, 0, 0, 1, 1)

        self.retranslateUi(resampler_widget)
        QtCore.QMetaObject.connectSlotsByName(resampler_widget)

    def retranslateUi(self, resampler_widget):
        _translate = QtCore.QCoreApplication.translate
        resampler_widget.setWindowTitle(_translate("resampler_widget", "Form"))
        self.lineEdit_2.setText(_translate("resampler_widget", "0"))
        self.label_36.setText(_translate("resampler_widget", "RESAMPLING"))
        self.listWidget_sourcelist_2.setToolTip(_translate("resampler_widget", "drag files from here to the \'Selected files\' list "))
        self.label_38.setText(_translate("resampler_widget", "Selected files"))
        self.label_41.setText(_translate("resampler_widget", "Choose file (drag right)"))
        self.label_31.setToolTip(_translate("resampler_widget", "select sampling rate of target files"))
        self.label_31.setText(_translate("resampler_widget", "target sampling rate (kS/s)"))
        self.comboBox_resample_targetSR.setItemText(0, _translate("resampler_widget", "20"))
        self.comboBox_resample_targetSR.setItemText(1, _translate("resampler_widget", "50"))
        self.comboBox_resample_targetSR.setItemText(2, _translate("resampler_widget", "100"))
        self.comboBox_resample_targetSR.setItemText(3, _translate("resampler_widget", "250"))
        self.comboBox_resample_targetSR.setItemText(4, _translate("resampler_widget", "500"))
        self.comboBox_resample_targetSR.setItemText(5, _translate("resampler_widget", "1250"))
        self.comboBox_resample_targetSR.setItemText(6, _translate("resampler_widget", "2000"))
        self.comboBox_resample_targetSR.setItemText(7, _translate("resampler_widget", "2500"))
        self.comboBox_resample_targetSR.setItemText(8, _translate("resampler_widget", "5000"))
        self.comboBox_resample_targetSR.setItemText(9, _translate("resampler_widget", "10000"))
        self.label_30.setText(_translate("resampler_widget", "Filename:"))
        self.label_29.setToolTip(_translate("resampler_widget", "baseline offset from automated baseline"))
        self.label_29.setText(_translate("resampler_widget", "target LO (kHz)"))
        self.lineEdit_resample_Gain.setText(_translate("resampler_widget", "0"))
        self.timeEdit_resample_startcut.setDisplayFormat(_translate("resampler_widget", "dd:HH:mm:ss"))
        self.lineEdit_resample_targetLO.setToolTip(_translate("resampler_widget", "LO frequency of the resampeled file in kHz"))
        self.label_33.setToolTip(_translate("resampler_widget", "trim file contents before that time in the first file in the list"))
        self.label_33.setText(_translate("resampler_widget", "Start cut"))
        self.graphicsView_resample.setToolTip(_translate("resampler_widget", "space for spectrum plot"))
        self.timeEdit_resample_stopcut.setDisplayFormat(_translate("resampler_widget", "dd:HH:mm:ss"))
        self.label_37.setToolTip(_translate("resampler_widget", "cut off last file in the list at this time"))
        self.label_37.setText(_translate("resampler_widget", "Stop cut"))
        self.label_28.setText(_translate("resampler_widget", "Freq corr %"))
        self.radioButton_advanced_sampling.setToolTip(_translate("resampler_widget", "Allow for resampling of whole file lists"))
        self.radioButton_advanced_sampling.setText(_translate("resampler_widget", "ADVANCED SAMPLING"))
        self.radioButton_resgain.setToolTip(_translate("resampler_widget", "Gain factor by which the signal will be multiplied in dB. Please check afterwards in \'View spectra\' if signal amplitude is below 1"))
        self.radioButton_resgain.setText(_translate("resampler_widget", "Manual Gain (dB)"))
        self.label_resample_targetfilename.setText(_translate("resampler_widget", "Target filename prefix"))
        self.lineEdit_resample_targetnameprefix.setToolTip(_translate("resampler_widget", "Base name of the fie; will be extended by number (optionally) and by the standard SDRUNO-postfix"))
        self.pushButton_resample_cancel.setToolTip(_translate("resampler_widget", "Cancel current operation"))
        self.pushButton_resample_cancel.setText(_translate("resampler_widget", "cancel"))
        self.pushButton_resample_resample.setToolTip(_translate("resampler_widget", "start resampling procedure"))
        self.pushButton_resample_resample.setText(_translate("resampler_widget", "Resample"))
        self.pushButton_resample_split2G.setToolTip(_translate("resampler_widget", "Split file in the list into 2GB parts"))
        self.pushButton_resample_split2G.setText(_translate("resampler_widget", "split/merge to 2GB"))
        self.checkBox_AutoMerge2G.setToolTip(_translate("resampler_widget", "merge to 2G tranches after resampling and delete intermediate files"))
        self.checkBox_AutoMerge2G.setText(_translate("resampler_widget", "Auto Merge 2G"))
        self.checkBox_merge_selectall.setToolTip(_translate("resampler_widget", "select/unselect all list elements"))
        self.checkBox_merge_selectall.setText(_translate("resampler_widget", "Select all"))
        self.checkBox_Cut.setText(_translate("resampler_widget", "Cut Start / End"))
        self.pushButton_resample_correctwavheaders.setText(_translate("resampler_widget", "correct times/nexfilenames"))
        self.pushButton_resample_GainOnly.setToolTip(_translate("resampler_widget", "start resampling procedure and splt reulting files in 2GB tranches"))
        self.pushButton_resample_GainOnly.setText(_translate("resampler_widget", "Gain only"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    resampler_widget = QtWidgets.QWidget()
    ui = Ui_resampler_widget()
    ui.setupUi(resampler_widget)
    resampler_widget.show()
    sys.exit(app.exec_())
