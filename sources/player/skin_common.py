"""Common look of the small-screen skins 2 and 3 (used by playerskinhandler_2/3):
uniform font roles and one 3-D button style for the player tab."""
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QIcon

# uniform font sizes (COHIWizard starter.resize_actor): every text gets the size of
# its role and is only made smaller if it does not fit into its field
FONT_ROLE_WIDGETS = {
    "lineEditCurTime": "large",
    "label_9": "small",       # 'Gain' below the gain slider
    "label_27": "small",      # 'Ampl' below the level meter
    "radioButton_LO_bias": "small",   # 'Offset'
    "label_LO_unit": "small",         # 'kHz' below 'Offset' (skin 2)
}


def font_roles(window_height):
    normal = max(11, round(window_height * 0.034))     # 16 px at 480 px window height
    return {"normal": normal, "small": max(11, round(normal * 0.8)),
            "large": round(normal * 1.6), "widgets": FONT_ROLE_WIDGETS}


# all buttons of the player tab in one muted blue with a raised 3-D look (light top
# edge, gradient from light to dark), except Shutdown; pressed / switched on:
# inverted gradient, looks pushed in
BUTTON_STYLE = (
    "QPushButton { color: white; font-weight: bold; padding: 2px;"
    " background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    " stop:0 #a9c3e0, stop:0.45 #6f93bb, stop:1 #46668c);"
    " border: 1px solid #2f4a66; border-top-color: #d3e1f0; border-left-color: #b8cde3;"
    " border-radius: 4px; }"
    "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    " stop:0 #b9cfe8, stop:0.45 #7fa1c6, stop:1 #557599); }"
    "QPushButton:pressed, QPushButton:checked { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    " stop:0 #3c5a7d, stop:0.55 #557599, stop:1 #7fa1c6);"
    " border-top-color: #2f4a66; border-left-color: #2f4a66; border-bottom-color: #b8cde3; }"
    "QPushButton:disabled { color: #e6ecf2; background: #a9b8c9; border-color: #a9b8c9; }")

# touch operation: large up/down buttons of the LO offset spin box (skin 2); the font
# of the number stays as it is. Only sizes: styling the buttons themselves (colour,
# border) makes Qt stop drawing the arrows
SPINBOX_STYLE = (
    "QSpinBox::up-button, QSpinBox::down-button { width: 34px; }"
    "QSpinBox::up-arrow, QSpinBox::down-arrow { width: 14px; height: 14px; }")

# the playlist toggle shows text in the button style instead of its two pictures
PLAYLIST_TEXT = {False: "Activate Playlist", True: "Select Files (drag)"}


def style_buttons(gui):
    for b in gui.tab_playrec.findChildren(QPushButton):
        if b.objectName() != "pushButton_Shutdown":
            b.setStyleSheet(BUTTON_STYLE)
    act = gui.pushButton_act_playlist
    act.setIcon(QIcon())
    act.setText(PLAYLIST_TEXT[act.isChecked()])
    act.toggled.connect(lambda on: act.setText(PLAYLIST_TEXT[on]))
    spin = getattr(gui, "spinBox_LOoffset", None)
    if spin is not None:
        spin.setStyleSheet(SPINBOX_STYLE)
