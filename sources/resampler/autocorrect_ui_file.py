# reading_file = open("./core/COHIWizard_GUI_v10_reduced.py", "r")

# new_file_content = ""
# for line in reading_file:
#     stripped_line = line.strip()
#     new_line = stripped_line.replace("font.setPointSize(10)", "font.setPointSize(12)")
#     new_file_content += new_line +"\n"
# reading_file.close()

# writing_file = open("./core/COHIWizard_GUI_v10_reduced.py", "w")
# writing_file.write(new_file_content)
# writing_file.close()
import re


#defining the replace method
def replace(file_path, text, subs, flags=0):
    with open(file_path, "r+") as file:
        #read the file contents
        file_contents = file.read()
        text_pattern = re.compile(re.escape(text), flags)
        file_contents = text_pattern.sub(subs, file_contents)
        file.seek(0)
        file.truncate()
        file.write(file_contents)

    
file_path = "./resampler/resampler_widget_skin_0.py"

text = "font.setPointSize(11)"
subs = "font.setPointSize(11)"
replace(file_path, text, subs)
text = "../"
subs = ""
replace(file_path, text, subs)
text = "icons/"
subs = ""
replace(file_path, text, subs)
text = "self.menubar = File(MainWindow)"
subs = "self.menubar = QtWidgets.QMenuBar(MainWindow)"
replace(file_path, text, subs)
text = "from file import File"
subs = "#from file import File"
replace(file_path, text, subs)
text = 'QPixmap("'
subs = 'QPixmap("./core/ressources/icons/'
replace(file_path, text, subs)