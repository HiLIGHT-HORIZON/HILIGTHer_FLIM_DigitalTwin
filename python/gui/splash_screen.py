import sys
import os
import subprocess
from PyQt6.QtWidgets import QSplashScreen, QApplication, QLabel
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter, QIcon
from PyQt6.QtCore import Qt, QTimer, QRect

class HILIGHTSplashScreen(QSplashScreen):
    """
    Custom splash screen for HILIGHTer Digital Twin.
    Features: 
    - Real-time log overprinting
    - Credits & Funding branding
    - Contributor extraction from git
    """
    def __init__(self, logo_path: str):
        base_pixmap = QPixmap(logo_path)
        scaled = base_pixmap.scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        canvas = QPixmap(scaled.size())
        canvas.fill(QColor("white"))
        painter = QPainter(canvas)
        painter.drawPixmap(0, 0, scaled)
        painter.end()
        super().__init__(canvas)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # Internal log buffer
        self.log_messages = ["Initializing HILIGHTer Engine..."]
        
        # Interactive Labels
        w = canvas.width()
        h = canvas.height()
        
        self.funding_label = QLabel(self)
        self.funding_label.setText(
            '<div style="text-align: right; color: #475569; font-family: \'Segoe UI\'; font-size: 10pt; font-weight: bold;">'
            'Project funded by EU HORIZON and UKRI<br>'
            '<a href="https://hilighthorizon.eu" style="color: #2563eb; text-decoration: none;">https://hilighthorizon.eu</a>'
            '</div>'
        )
        self.funding_label.setOpenExternalLinks(True)
        self.funding_label.setGeometry(w - 550, h - 80, 530, 60)
        self.funding_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.funding_label.setStyleSheet("background: transparent;")
        
        self.creator_label = QLabel(self)
        self.creator_label.setText(
            '<div style="text-align: right; color: #475569; font-family: \'Segoe UI\'; font-size: 10pt;">'
            'Project initiated by Dr Alessandro Esposito<br>'
            'Brunel University of London<br>'
            '<a href="https://quantitative-biology.org" style="color: #2563eb; text-decoration: none;"><b>https://quantitative-biology.org</b></a>'
            '</div>'
        )
        self.creator_label.setOpenExternalLinks(True)
        self.creator_label.setGeometry(w - 650, h - 150, 630, 60)
        self.creator_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.creator_label.setStyleSheet("background: transparent;")

        
        # Attempt to get contributors from Git
        self.contributors = self._get_git_contributors()
        
    def _get_git_contributors(self):
        """Pulls unique names and github-style handles from git log."""
        try:
            # Fallback to defaults first, then append from log
            defaults = [("Alessandro Esposito", "ae275"), ("Conor Treacy", "conortreacy")]
            cmd = "git log --format='%aN|%aE' | sort -Unique"
            # Since git log | sort -Unique works in powershell, let's try calling it via shell
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8')
            
            contributors = set()
            for line in output.strip().split('\n'):
                if not line or '|' not in line: continue
                name, email = line.split('|')
                # Extract handle from email if possible (users.noreply.github.com style)
                handle = ""
                if "users.noreply.github.com" in email:
                    handle = email.split('@')[0]
                contributors.add((name, handle))
            
            # Combine
            final_set = set(defaults)
            for c in contributors:
                final_set.add(c)
            
            # Sort by name
            return sorted(list(final_set))
        except:
            return [("Alessandro Esposito", "ae275"), ("Conor Treacy", "c-treacy")]

    def log(self, text: str):
        """Real-time log update over the splash screen."""
        self.log_messages.append(text)
        if len(self.log_messages) > 15:
            self.log_messages.pop(0)
        
        # Re-render
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter: QPainter):
        """Draw branding, credits, and logs."""
        super().drawContents(painter)
        
        w = self.width()
        h = self.height()

        log_rect = QRect(20, 20, w - 40, min(220, max(140, h // 3)))

        # 1. Logs (Top Left)
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Consolas", 9))
        log_txt = "\n".join([f"> {m}" for m in self.log_messages])
        painter.drawText(log_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, log_txt)

        # 2. Credits (Bottom Right)
        # Now handled by QLabels in __init__ for interactivity.

        # 3. Contributors (Bottom Left)
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(20, h - 140, 200, 25, Qt.AlignmentFlag.AlignLeft, "Contributors:")
        
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#475569"))
        y_pos = h - 110
        for name, handle in self.contributors:
            handle_str = f" (@{handle})" if handle else ""
            painter.drawText(20, y_pos, 400, 20, Qt.AlignmentFlag.AlignLeft, f"{name}{handle_str}")
            y_pos += 20
