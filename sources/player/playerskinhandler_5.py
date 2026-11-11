#class for skin handling

class skinhandler():


    def resize_ui(gui):
        # This function would contain logic to redirect UI items to the appropriate skin directories
        # For example, it could check for the existence of certain files in the skin directory and redirect accordingly
        # print("Resize Player UI to screen size")
        # gui.showMaximized()
        pass

    def redirect_ui_items(gui):
        # This function redirects new items defined in the respective skin to the ones used in skin 1 (default UI items set)
        # when defining new skins which contain elements other than those used in the reference skin (skin 1), but with the same function, ehile the original ones are hidden, 
        # then redirect their signals to those of the original items
        # Example:        There might be a new item in skin 2 called pushButton_Fileopen, which does not exist in skin 1, 
        # Then we can redirect the signal of pushButton_Fileopen to the same function as File_Open in the manubar of skin 1 (relayed via an action), 
        # so that the functionality is preserved across skins.
        # the redirection would then read:
        # gui.pushButton_Fileopen.clicked.connect(gui.actionFile_open.trigger)

        # print("Redirecting global UI items to skin items")


        pass

    def reorganize_canvas(gui,plot_widget):
        # This function would contain logic to redirect UI items to the appropriate skin directories
        # For example, it could check for the existence of certain files in the skin directory and redirect accordingly
        # rows 1-4 (below the CONFIGURATION button, above the modulator type) became free
        # when the configuration widgets moved to the configuration dialog
        print("Reorganizing canvas for skin to 1,12,4,2")
        gui.gridLayout_10.addWidget(plot_widget,1,12,4,2)
        pass

    def maxsize():
        return 20

    # uniform font sizes as in skins 2/3 (COHIWizard starter.resize_actor): every text
    # gets the size of its role and is only made smaller if it does not fit; the
    # window of skin 5 is larger, hence a smaller factor (16 px at 860 px)
    FONT_ROLE_WIDGETS = {
        "lineEditCurTime": "large",
    }

    def font_roles(window_height):
        normal = max(11, min(20, round(window_height * 0.0186)))
        return {"normal": normal, "small": max(11, round(normal * 0.8)),
                "large": round(normal * 1.6), "widgets": skinhandler.FONT_ROLE_WIDGETS}