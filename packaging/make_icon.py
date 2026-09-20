"""Write a placeholder 256x256 PNG icon (flat blue square, white 'L') with PyQt5."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
pix = QtGui.QPixmap(256, 256)
pix.fill(QtCore.Qt.transparent)
p = QtGui.QPainter(pix)
p.setRenderHint(QtGui.QPainter.Antialiasing)
p.setBrush(QtGui.QColor("#1f6feb"))
p.setPen(QtCore.Qt.NoPen)
p.drawRoundedRect(8, 8, 240, 240, 48, 48)
font = QtGui.QFont("Sans", 140, QtGui.QFont.Bold)
p.setFont(font)
p.setPen(QtGui.QColor("white"))
p.drawText(pix.rect(), QtCore.Qt.AlignCenter, "L")
p.end()
pix.save(sys.argv[1])
