from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

class stepURL(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("NXM Collection Downloader - Step 1")
		self.setMinimumWidth(400)

		layout = QVBoxLayout()

		self.label = QLabel("Enter Nexus Collection URL:")
		layout.addWidget(self.label)

		self.url_input = QLineEdit()
		self.url_input.setPlaceholderText("https://next.nexusmods.com/.../collections/.../")
		layout.addWidget(self.url_input)

		self.submit_btn = QPushButton("Submit")
		self.submit_btn.clicked.connect(self.get_url)
		layout.addWidget(self.submit_btn) 

		self.setLayout(layout)

	def get_url(self):
		input = self.url_input.text().strip()
		input = input.replace("http://", "https://")
		for suffix in ["/mods", "/comments", "/changelog", "/bugs"]:
			if input.endswith(suffix):
				input = input[: -len(suffix)]

		qDebug(f"[NXMColDL] URL entered: {input}")
		return input