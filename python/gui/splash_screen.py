import sys
import os
import subprocess
from PyQt6.QtWidgets import QSplashScreen, QApplication
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
        pixmap = QPixmap(logo_path).scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio)
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        # Internal log buffer
        self.log_messages = ["Initializing HILIGHTer Engine..."]
        
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
        
        # Transparent overlay for better readability
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 60))

        # 1. Logs (Top Left)
        painter.setPen(QColor("#cbd5e1")) # Slate-300
        painter.setFont(QFont("Consolas", 9))
        log_txt = "\n".join([f"> {m}" for m in self.log_messages])
        painter.drawText(20, 30, w - 40, h - 300, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, log_txt)

        # 2. Credits (Bottom Right)
        # Funded by EU & UKRI
        painter.setPen(QColor("#94a3b8")) # Slate-400
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        funding_rect = QRect(w - 450, h - 80, 430, 60)
        painter.drawText(funding_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, 
                         "Project funded by EU HORIZON and UKRI\nhttps://hilighthorizon.eu/")

        # Created by
        painter.setFont(QFont("Segoe UI", 11))
        creator_rect = QRect(w - 450, h - 130, 430, 40)
        painter.drawText(creator_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, 
                         "Project created by Dr Alessandro Esposito")

        # 3. Contributors (Bottom Left)
        painter.setPen(QColor("#f1f5f9")) # Slate-100
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(20, h - 140, 200, 25, Qt.AlignmentFlag.AlignLeft, "Contributors:")
        
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#94a3b8")) # Slate-400
        y_pos = h - 110
        for name, handle in self.contributors:
            handle_str = f" (@{handle})" if handle else ""
            painter.drawText(20, y_pos, 400, 20, Qt.AlignmentFlag.AlignLeft, f"{name}{handle_str}")
            y_pos += 20
