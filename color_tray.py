#!/bin/python3

import wx.adv
import glob, os

import re
import subprocess
from functools import partial

SCRIPT_ROOT = os.path.dirname(os.path.realpath(__file__))
TRAY_TOOLTIP = 'Color Management'
TRAY_ICON = SCRIPT_ROOT+'/icon.png'

dispwincmd="/home/cedric/apps/Argyll_V2.1.2/bin/dispwin"

def get_display_profiles():
    colrmgr = subprocess.run(["colormgr", "get-devices-by-kind", "display"],
        check = True,
        stdout=subprocess.PIPE)

    devices = []
    currentdev = None
    lines = [b.decode('utf-8') for b in colrmgr.stdout.split(b'\n')]

    for i, line in enumerate(lines):
        if "Object Path:" in line[:12]:
            if currentdev is not None:
                devices.append(currentdev)
            currentdev = {}
            currentdev["profiles"] = []
            currentdev["path"] = line[15:]
        if line.startswith("Model:"):
            currentdev["model"] = line[15:]
        if line.startswith("Enabled:"):
            currentdev["enabled"] = line[15:]
        if line.startswith("Serial:"):
            currentdev["serial"] = line[15:]
        if line.startswith("Device ID:"):
            currentdev["deviceid"] = line[15:]
        if line.startswith("Metadata:      XRANDR_name="):
            currentdev["xrandr_name"] = line[27:]
        if "Profile " in line[:8]:
            profileid = line[15:]
            profilepath = lines[i+1][15:]
            currentdev["profiles"].append((profileid, profilepath))
    if currentdev is not None:
        devices.append(currentdev)
    return devices

def get_dispwin_monitor_id(xrandr_name):
    dspwin = subprocess.run([dispwincmd, "-h"],
            check = False,
            stderr=subprocess.PIPE)
    lines = [b.decode('utf-8') for b in dspwin.stderr.split(b'\n')]

    for i, line in enumerate(lines):
        if xrandr_name in line:
            match = re.search("[\d]+ =", line)
            monitor_id = line[match.start():match.end()-1]
            return monitor_id
            

def make_device_default(path, id, xrandr_name, iccpath):
    xrandr_id = get_dispwin_monitor_id(xrandr_name)
    if id != "Disable":
        dspwin = subprocess.run([dispwincmd, "-d", xrandr_id, "-v", "-c", "-I", iccpath],
            check = False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        colrmgr = subprocess.run(["colormgr", "device-set-enabled", path, "True"],
            check = True,
            stdout=subprocess.PIPE)
        colrmgr = subprocess.run(["colormgr", "device-make-profile-default", path, id],
            check = True,
            stdout=subprocess.PIPE)
    else:
        dspwin = subprocess.run([dispwincmd, "-d", xrandr_id, "-U"],
            check = False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        colrmgr = subprocess.run(["colormgr", "device-set-enabled", path, "False"],
            check = True,
            stdout=subprocess.PIPE)

class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        self.frame = frame
        super(TaskBarIcon, self).__init__()
        self.set_icon(TRAY_ICON)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

    def create_color_menu_item(self, menu, item, path, xrandr_name, disabled):
        label = item[1].split("/")[-1]
        if disabled:
            label = "* " + label
        menuitem = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, partial(self.on_change_profile, (path, item, xrandr_name, item[1])), id=menuitem.GetId())
        menu.Append(menuitem)
        if disabled:
            menuitem.Enable(False)
        return menuitem

    def create_menu_item(self, menu, label, func):
        menuitem = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=menuitem.GetId())
        menu.Append(menuitem)
        return menuitem

    def create_submenu(self, menu, label, items):
        first = True
        if items["enabled"] == "No":
            first = False
        submenu = wx.Menu()
        menu.AppendSubMenu(submenu, label[7:])
        for item in items["profiles"]:
            self.create_color_menu_item(submenu, item, items["path"], items["xrandr_name"], first)
            first = False
        self.create_color_menu_item(submenu, ["Disable", "/Disable"], items["path"], items["xrandr_name"], items["enabled"] == "No")

    def CreatePopupMenu(self):
        displays = get_display_profiles()
        menu = wx.Menu()
        for display in displays:
            self.create_submenu(menu, display["deviceid"], display)
        menu.AppendSeparator()
        self.create_menu_item(menu, 'Exit', self.on_exit)
        return menu

    def set_icon(self, path):
        icon = wx.Icon(wx.Bitmap(path))
        self.SetIcon(icon, TRAY_TOOLTIP)

    def on_left_down(self, event):
        pass

    def on_exit(self, event):
        wx.CallAfter(self.Destroy)
        self.frame.Close()

    def on_change_profile(self, sel, e):
        path = sel[0]
        profile = sel[1][0]
        xrandr_name = sel[2]
        iccpath = sel[3]
        make_device_default(path, profile, xrandr_name, iccpath)

class App(wx.App):
    def OnInit(self):
        frame=wx.Frame(None)
        self.SetTopWindow(frame)
        TaskBarIcon(frame)
        return True

def main():
    app = App(False)
    app.MainLoop()

if __name__ == '__main__':
    main()