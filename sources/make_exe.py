"""Make file for compiling the COHIWizard with pyinstaller importing hidden imports (submodules)
This is necessary for versions of the COHIWizard after introducing dynamic impot of the modules"""

import subprocess
import yaml
import importlib
import os

def load_config_from_yaml(file_path):
    """load module configuration from yaml file"""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

print("################################################################################")
config = load_config_from_yaml("config_modules.yaml")
sub_module = "modules"
mod_base = {'player':'playrec'}
config['modules'] = {**mod_base, **config['modules']}
widget_base = {'player': 'Player'}
config['module_names'] = {**widget_base, **config['module_names']}
list_mvct_directories = list(config['modules'].keys())
#get list of corresponding mvct modules
list_mvct_modules = list(config['modules'].values())
#add dict of widget modules to config
aux_dict = {}
for ix in range(len(list_mvct_directories)):
    aux_dict[list_mvct_directories[ix]] = list_mvct_directories[ix] + "_widget"
config["widget"] = aux_dict
#get list of corresponding widget modules
list_widget_modules = list(config['widget'].values())

#compose pyinstaller command
#hooks path
hooks_path = os.path.join(os.getcwd())
#root string
#command = 'pyinstaller --icon=COHIWizard_ico4.ico --onefile --log-level=DEBUG --additional-hooks-dir=hooks --paths=' + hooks_path + ' -F COHIWizard.py '#pyinstaller --onefile --additional-hooks-dir=hooks dein_script.py
command = 'pyinstaller --icon=COHIWizard_ico4.ico --onefile COHIWizard.py --paths=. '#pyinstaller --onefile --additional-hooks-dir=hooks dein_script.py
#command = 'pyinstaller --icon=COHIWizard_ico4.ico --onefile sources/COHIWizard.py --paths=sources'
# include hidden imports according to config_modules.yaml
for ix in range(len(list_mvct_directories)): 
    module = list_mvct_directories[ix] + "." + list_mvct_modules[ix] 
    command += (f' --hidden-import={module}')
for ix in range(len(list_mvct_directories)): 
    module = list_mvct_directories[ix] + "." + list_widget_modules[ix] 
    command += (f' --hidden-import={module}')
if os.path.exists(os.path.join(os.getcwd(),'dev_drivers')):
    list_dev_drivers = list(config["dev_workers"])
    for ix, key in enumerate(list_dev_drivers): 
        SDR_controller = "dev_drivers." + key + ".SDR_control" 
        command += (f' --hidden-import={SDR_controller}')
        dev_worker = "dev_drivers." + key + ".cohi_playrecworker"
        command += (f' --hidden-import={dev_worker}')
    #command += ' --hidden-import=dev_drivers'
    #####TODO: hidden imports for dev_drivers über dev_workers und SDR_controllers einbinden:
    #### driverliste abarbeiten und --hidden import strings generieren
#command += " > pyinstaller.log"
#execute command
subprocess.run(command)