import sys
import os

fp_freeform = 'python/gui/widgets/freeform_irf_editor.py'
with open(fp_freeform, 'r', encoding='utf-8') as f:
    text = f.read()

# Remove lbl_hint references
text = text.replace('self.lbl_hint = QLabel("Click a point to select it. Drag to move. Click empty space then Add Point to insert.")', '')
text = text.replace('self.lbl_hint.setWordWrap(True)', '')
text = text.replace('info_row.addWidget(self.lbl_hint, 1)', 'info_row.addStretch(1)')
text = text.replace('self.lbl_hint.setStyleSheet(f"color: {text};")', '')

with open(fp_freeform, 'w', encoding='utf-8') as f:
    f.write(text)

fp_controls = 'python/gui/widgets/controls.py'
with open(fp_controls, 'r', encoding='utf-8') as f:
    ctext = f.read()

old_layout = '''        freeform_container_layout.addWidget(self.lbl_freeform_help, 0, Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(freeform_header, 0, Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(self.freeform_editor)
        laser_layout.addRow("", freeform_container)'''
        
new_layout = '''        freeform_container_layout.addWidget(freeform_header, 0, Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(self.lbl_freeform_help, 0, Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(self.freeform_editor)
        laser_layout.addRow(freeform_container)'''

if old_layout in ctext:
    ctext = ctext.replace(old_layout, new_layout)
else:
    print("Could not find old_layout snippet in controls.py!")

with open(fp_controls, 'w', encoding='utf-8') as f:
    f.write(ctext)

print('Updated both files.')
