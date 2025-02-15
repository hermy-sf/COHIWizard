# Software architecture

The software contains a core module and, for each tab of the GUI, an individual additional module which handles all the methods required under a tab. Additionally there are auxiliary modules which implement helper classes which are accessed by one or more of the tab modules.

The software architecture is built up according to the design pattern model-view-controller. This means that each module X contains three base classes X_m, X_c and X_v, '_m', '_c' and '_v' standing for 'model', 'control' and 'view'. There may also be additional classes for thread workers, as several long-lasting processes need to be carried out in separate threads, apart from the main thread of the GUI.

'model', 'control' and 'view' are instantiated in the __main__ section of COHIWizard.py as:

        X_m = X.X_m()
        X_c = X.X_c(X_m)
        X_v = X.X_v(TabUI,X_c,X_m)

The model class just holds all the data sherd by the three classes. The control class implements all methods for process control and the view class implements all (graphical) input and display functions of the corresponding tab. X-C has no direct access to the GUI elements and must communicate respective queries to X_v by signalling. This structure guarantees that all three classes have access to the data contained in the model class but otherwise encapsulate distinct responsabilites in a clear hierarchy. 

TabUI is an instance of a QT Widget which is defined in the additional module 

	X_widget.py 

which has to be defined for each tab. This module implements all PyQT widgets of the respective tab in the GUI ans is typically generated with Qt Designer and defines a class Ui_X_widget(object). The widget is constructed via its method setupUi. The instance is then added to a new tab in the main GUI if the module X is installed in the main pprogram COHIWizard.py


The core module is instantiated somewhat differently.

        xcore_m = core_m()
        xcore_c = core_c(xcore_m)
        xcore_v = core_v(gui,xcore_c,xcore_m)

gui is an instance of type QMainWindow which is generated in a starter class which implements the main GUI window and the tab for the player module.


Methods of classes in different modules cannot access each other directly. If there is the need for transferring data between modules, only signalling is being used. Methods of other module's classes must be connected explicitly to these signals to receive the data. In order to simplify the communication each X_v and V_c class implements a Relay signal SigRelay(str, object) of type pyqtSignal(str,object) and an rx-handler method rxh(self,_key,_value) which can be modified so as to react to specific Relay signals.

`SigRelay(str, object)`:

str is a string referring to the modulename X where the information should be sent to (or '_all_' if sent unspecifically) and object is a key-value pair ["key",value] where key indicates the type of action at the target module and value some parameter if required.

`rxh(self,_key,_value)`:



