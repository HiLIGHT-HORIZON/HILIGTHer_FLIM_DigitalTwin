import sys
import os

with open('python/gui/splash_screen.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('https://hilighthorizon.eu/', 'https://hilighthorizon.eu')

old_creator = """        self.creator_label.setText(
            '<div style="text-align: right; color: #475569; font-family: \\'Segoe UI\\'; font-size: 11pt;">'
            'Project initiated by Dr Alessandro Esposito (Brunel University of London)<br>'
            'Laboratory page: <a href="https://quantitative-biology.org" style="color: #2563eb; text-decoration: none;">quantitative-biology.org</a>'
            '</div>'
        )"""

new_creator = """        self.creator_label.setText(
            '<div style="text-align: right; color: #475569; font-family: \\'Segoe UI\\'; font-size: 10pt;">'
            'Project initiated by Dr Alessandro Esposito<br>'
            'Brunel University of London<br>'
            '<a href="https://quantitative-biology.org" style="color: #2563eb; text-decoration: none;"><b>https://quantitative-biology.org</b></a>'
            '</div>'
        )"""
if old_creator in text:
    text = text.replace(old_creator, new_creator)
else:
    print("Could not find old_creator string in splash_screen.py!")

with open('python/gui/splash_screen.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open('python/gui/widgets/controls.py', 'r', encoding='utf-8') as f:
    ctext = f.read()

old_btn = '''        self.btn_sweep_export = self._make_icon_button(QStyle.StandardPixmap.SP_DialogSaveButton, "Export the current editable sweep defaults to a JSON file.", "Export")
        self.btn_sweep_reset = self._make_icon_button(QStyle.StandardPixmap.SP_DialogResetButton, "Reset the active sweep-default JSON back to the installation defaults.", "Reset")'''
new_btn = '''        self.btn_sweep_export = self._make_icon_button(QStyle.StandardPixmap.SP_DriveFDIcon, "Export the current editable sweep defaults to a JSON file.", "Export")
        self.btn_sweep_reset = self._make_icon_button(QStyle.StandardPixmap.SP_RestoreDefaultsButton, "Reset the active sweep-default JSON back to the installation defaults.", "Reset")'''
if old_btn in ctext:
    ctext = ctext.replace(old_btn, new_btn)
else:
    print("Could not find old_btn string in controls.py!")

with open('python/gui/widgets/controls.py', 'w', encoding='utf-8') as f:
    f.write(ctext)

print('Updated both files.')
