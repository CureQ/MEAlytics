MEAlytics has two main ways of installation; running MEAlytics as a Python package, or installation using a Windows installer.

# Using a Windows Installer
MEAlytics also provides a Windows installer, which provides the simplest way of installing MEAlytics on a Windows machine. Installers for every version can be found in the [releases tab](https://github.com/CureQ/MEAlytics/releases).<br>
For the installer, the package is bundled into an executable using PyInstaller, and turned into an installer using Inno Setup.

# Installing Python
A Python interpreter is required to run MEAlytics, the interpreter using the official python installer. All python versions can be found on [https://www.python.org/downloads/](https://www.python.org/downloads/). MEAlytics has been developed and tested on python 3.14, but will most likely also work on other python 3.8+ versions.<br>
There are plenty of guide available for this process online, to check if your installation was succesful, you can run:
```console
C:\>python --version
Python 3.14.0

C:\>pip --version
pip 23.3.1
```
If both outputs look like this (it can be different versions) both python and pip have been successfully installed and are recognised by the system.<br>
<br>

## Installing MEAlytics
Once both python and pip have been installed, acquiring the MEA analysis tool should be simple. For the next step we will use pip to install the tool.<br>
First, open the command prompt, then enter:
```console
pip install MEAlytics
```
Pip will now collect the MEAlytics package from the internet, collect and install dependencies and the library. The last few lines should look like this:
```console
Installing collected packages: MEAlytics
Successfully installed MEAlytics-0.1.0
```
MEAlytics is now successfully installed on your machine and can be executed from a python script.

## Upgrade Library
MEAlytics might receive further updates to enhance the analysis, or fix problems. To check the current version of the library, open the command prompt, and enter:
```console
C:\> MEAlytics --version    
MEAlytics - Version: 0.1.0
```

The most recent available version of the library can be found on the [pypi page](https://pypi.org/project/MEAlytics/). The library can be upgraded using the command:
```console
pip install mealytics –upgrade
```
This will upgrade the library to the newest available version.

```console
C:\ > pip install mealytics --upgrade
Successfully installed mealytics-0.1.0
```
