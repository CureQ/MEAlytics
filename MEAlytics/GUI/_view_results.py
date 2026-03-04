# Imports
import os
from functools import partial
import json
import webbrowser
from tkinter import *
from tkinter import filedialog
from importlib.metadata import version
import traceback
import threading

# External libraries
import h5py
import customtkinter as ctk
from CTkToolTip import *
from CTkMessagebox import CTkMessagebox
from CTkColorPicker import *

# GUI components
from MEAlytics.GUI._single_electrode_view import single_electrode_view
from MEAlytics.GUI._whole_well_view import whole_well_view
from MEAlytics.GUI._heatmap import heatmap_frame

class view_results(ctk.CTkFrame):
    """
    Allow the user to view the results of the MEA analysis
    """
    def __init__(self, parent, folder, rawfile):
        super().__init__(parent)

        self.folder=folder
        self.rawfile=rawfile
        self.parent=parent

        self.parent.title(f"MEAlytics - Version: {version('MEAlytics')} - {self.folder}")

        self.tab_frame=ctk.CTkTabview(self, anchor='nw')
        self.tab_frame.grid(column=0, row=0, sticky='nesw', pady=10, padx=10, columnspan=2)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_frame.add("Single Electrode View")
        self.tab_frame.tab("Single Electrode View").grid_columnconfigure(0, weight=1)
        self.tab_frame.tab("Single Electrode View").grid_rowconfigure(0, weight=1)

        self.tab_frame.add("Whole Well View")
        self.tab_frame.tab("Whole Well View").grid_columnconfigure(0, weight=1)
        self.tab_frame.tab("Whole Well View").grid_rowconfigure(0, weight=1)

        self.tab_frame.add("Heatmap")
        self.tab_frame.tab("Heatmap").grid_columnconfigure(0, weight=1)
        self.tab_frame.tab("Heatmap").grid_rowconfigure(0, weight=1)

        # sev = single electrode view
        # wwv = whole well view

        # Load files
        self.parameters=open(f"{folder}/parameters.json")
        self.parameters=json.load(self.parameters)
        with h5py.File(rawfile, 'r') as hdf_file:
            self.datashape=hdf_file["Data/Recording_0/AnalogStream/Stream_0/ChannelData"].shape
        well_amnt = self.datashape[0]/self.parameters["electrode amount"]

        """Single electrode view"""
        self.selected_well=1
        sev_well_button_frame=ctk.CTkFrame(self.tab_frame.tab("Single Electrode View"))
        sev_well_button_frame.grid(row=0, column=0, pady=10, padx=10, sticky='nesw')

        sev_electrode_button_frame=ctk.CTkFrame(self.tab_frame.tab("Single Electrode View"))
        sev_electrode_button_frame.grid(row=0, column=1, pady=10, padx=10, sticky='nesw')
        
        # Wellbuttons
        self.xwells, self.ywells = parent.calculate_well_grid(well_amnt)
        self.sev_wellbuttons=[]
        i=1

        for y in range(self.ywells):
            for x in range(self.xwells):
                well_btn=ctk.CTkButton(master=sev_well_button_frame, text=i, command=partial(self.set_selected_well, i), height=100, width=100, font=ctk.CTkFont(size=25))
                well_btn.grid(row=y, column=x, sticky='nesw')
                self.sev_wellbuttons.append(well_btn)
                i+=1

        # Electrode buttons
        electrode_amnt = self.parameters["electrode amount"]

        electrode_layout = parent.calculate_electrode_grid(electrode_amnt)

        i = 1
        electrodebuttons=[]
        for x in range(electrode_layout.shape[0]):
            for y in range(electrode_layout.shape[1]):
                if electrode_layout[x,y]:
                    electrode_btn=ctk.CTkButton(master=sev_electrode_button_frame, text=i, command=partial(self.open_sev_tab, i), height=100, width=100, font=ctk.CTkFont(size=25))
                    electrode_btn.grid(row=x, column=y, sticky='nesw')
                    electrodebuttons.append(electrode_btn)
                    i+=1

        """Whole well view"""
        wwv_well_button_frame=ctk.CTkFrame(self.tab_frame.tab("Whole Well View"))
        wwv_well_button_frame.grid(row=0, column=0, pady=10, padx=10, sticky='nesw')

        wwv_wellbuttons=[]
        i=1

        for y in range(self.ywells):
            for x in range(self.xwells):
                well_btn=ctk.CTkButton(master=wwv_well_button_frame, text=i, command=partial(self.open_wwv_tab, i), height=100, width=100, font=ctk.CTkFont(size=25))
                well_btn.grid(row=y, column=x)
                wwv_wellbuttons.append(well_btn)
                i+=1

        """Heatmap"""
        open_hm_button = ctk.CTkButton(master=self.tab_frame.tab("Heatmap"), text='Open Heatmap', command=self.open_heatmap_thread)
        open_hm_button.grid(row=0, column=0)

        # Button to return to main menu
        return_to_main = ctk.CTkButton(master=self, text="Return to main menu", command=lambda: self.parent.show_frame(self.parent.home_frame), fg_color=parent.gray_1)
        return_to_main.grid(row=1, column=0, pady=10, padx=10, sticky='w')

        layout_warning = ctk.CTkButton(master=self, text="Warning: The well/electrode layout is auto-generated and may not match the physical plate exactly. Click here for details.", command=lambda: webbrowser.open_new("https://cureq.github.io/MEAlytics/supported_plates/"), fg_color=parent.gray_1)
        layout_warning.grid(row=1 , column=1, pady=10, padx=10, sticky='e')

   
    def set_selected_well(self, i):
        self.selected_well=i
        for j in range(len(self.sev_wellbuttons)):
            self.sev_wellbuttons[j].configure(fg_color=self.parent.theme["CTkButton"]["fg_color"][1])
        self.sev_wellbuttons[i-1].configure(fg_color=self.parent.theme["CTkButton"]["hover_color"][1])

    def open_sev_tab(self, electrode):
        single_electrode_view(self.parent, self.folder, self.rawfile, self.selected_well, electrode)

    def open_wwv_tab(self, well):
        whole_well_view(self.parent, self.folder, well)

    def open_heatmap_thread(self):
        hm_thread = threading.Thread(target=self.open_heatmap)
        hm_thread.start()

    def open_heatmap(self):
        heatmap_frame(master=self.tab_frame.tab("Heatmap"), parent=self.parent, datashape=self.datashape, parameters=self.parameters, xwells=self.xwells, ywells=self.ywells, folder=self.folder, tabwidget=self.tab_frame)