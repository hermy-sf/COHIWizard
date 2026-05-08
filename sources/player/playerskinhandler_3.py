#class for skin handling

class skinhandler():


    def resize_ui(gui):

        print("Resize Player UI to screen size")
        gui.showMaximized()
        pass

    def redirect_ui_items(gui):
        # This function redirects new items defined in the respective skin to the ones used in skin 1 (default UI items set)
        # when defining new skins which contain elements other than those used in the reference skin (skin 1), but with the same function, ehile the original ones are hidden, 
        # then redirect their signals to those of the original items
        # Here: There a new item called pushButton_Fileopen, which is not present in skin 1, 
        # We redirect the signal of pushButton_Fileopen to the same function as File Open in the menu bar,
        # the menu bar, in turn, is set invisible, so that the user only sees the new button.
        # which is present in skin 1, and which is used in skin 1, so that the functionality is preserved across skins.
        gui.pushButton_Fileopen.clicked.connect(gui.actionFile_open.trigger)
        gui.menubar.setVisible(False)
        print("Redirecting global UI items to skin items")


        pass

    def reorganize_canvas(gui,plot_widget):
        # This function would contain logic to redirect UI items to the appropriate skin directories
        # For example, it could check for the existence of certain files in the skin directory and redirect accordingly
        print("Reorganizing canvas for skin to 8,13,3,2")
        gui.gridLayout_10.addWidget(plot_widget,8,13,3,2)
        pass

    def maxsize():
        return 50
