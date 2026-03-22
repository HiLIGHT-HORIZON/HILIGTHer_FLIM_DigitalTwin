import re

with open('python/gui/splash_screen.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure to import QLabel
if 'QLabel' not in text:
    text = text.replace('QSplashScreen, QApplication', 'QSplashScreen, QApplication, QLabel')


init_injection = '''        # Internal log buffer
        self.log_messages = ["Initializing HILIGHTer Engine..."]
        
        # Interactive Labels
        w = canvas.width()
        h = canvas.height()
        
        self.funding_label = QLabel(self)
        self.funding_label.setText(
            '<div style="text-align: right; color: #475569; font-family: \\'Segoe UI\\'; font-size: 10pt; font-weight: bold;">'
            'Project funded by EU HORIZON and UKRI<br>'
            '<a href="https://hilighthorizon.eu/" style="color: #2563eb; text-decoration: none;">https://hilighthorizon.eu/</a>'
            '</div>'
        )
        self.funding_label.setOpenExternalLinks(True)
        self.funding_label.setGeometry(w - 550, h - 80, 530, 60)
        self.funding_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.funding_label.setStyleSheet("background: transparent;")
        
        self.creator_label = QLabel(self)
        self.creator_label.setText(
            '<div style="text-align: right; color: #475569; font-family: \\'Segoe UI\\'; font-size: 11pt;">'
            'Project initiated by Dr Alessandro Esposito (Brunel University of London)<br>'
            'Laboratory page: <a href="https://quantitative-biology.org" style="color: #2563eb; text-decoration: none;">quantitative-biology.org</a>'
            '</div>'
        )
        self.creator_label.setOpenExternalLinks(True)
        self.creator_label.setGeometry(w - 650, h - 150, 630, 60)
        self.creator_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.creator_label.setStyleSheet("background: transparent;")
'''

text = text.replace('''        # Internal log buffer
        self.log_messages = ["Initializing HILIGHTer Engine..."]''', init_injection)


draw_code_to_remove = '''        # 2. Credits (Bottom Right)
        # Funded by EU & UKRI
        painter.setPen(QColor("#475569"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        funding_rect = QRect(w - 450, h - 80, 430, 60)
        painter.drawText(funding_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, 
                         "Project funded by EU HORIZON and UKRI\\nhttps://hilighthorizon.eu/")

        # Created by
        painter.setFont(QFont("Segoe UI", 11))
        creator_rect = QRect(w - 450, h - 130, 430, 40)
        painter.drawText(creator_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, 
                         "Project created by Dr Alessandro Esposito")'''

text = text.replace(draw_code_to_remove, '        # 2. Credits (Bottom Right)\n        # Now handled by QLabels in __init__ for interactivity.')


with open('python/gui/splash_screen.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Splash screen updated successfully.")
