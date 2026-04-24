The graphical user interface is the simplest way to communicate with the library. If you have installed MEAlytics using Python, the GUI can be launched in multiple ways:

## Launch from command prompt
Firstly, the GUI can be launched from the command prompt. Simply open the command prompt, and enter “mealytics”.

```console
C:\Users>mealytics
```

or

```console
C:\Users>python -m MEAlytics
```

The GUI should appear on your screen.

<img src="../assets/images/mealytics_homescreen.png" width="429" height="254">

## Create shortcuts
This process can be simplified by creating shortcuts that in essence perform the same process. In the command prompt, enter “mealytics --create-shortcut”.

```console
C:\Users>mealytics --create-shortcut
Desktop shortcut created at C:\Users\Desktop\MEAlytics.lnk
```

The output should look like this, and a shortcut should appear on your desktop:
 
<img src="../assets/images/mealytics_on_desktop.png">

If you are on a Windows machine, the shortcut will also be added to the start menu.
The shortcut can also be added to the taskbar by pressing “Pin to taskbar”.

## Launch from python script
Lastly, the GUI can be launched from a python script. Create a python file and execute the following code:
```python 
from MEAlytics.GUI.mea_analysis_tool import MEA_GUI

if __name__=="__main__":
    MEA_GUI()
```
The GUI should always be opened inside the ```if __name__ == '__main__'``` guard when using multiprocessing.
