import re
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from .api import fetchRevisions
from . import var

class stepURL(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("NXM Collection Downloader - Enter URL")
		self.setMinimumWidth(400)

		layout = QVBoxLayout()

		self.label = QLabel("Enter Nexus Collection URL:")
		layout.addWidget(self.label)

		self.url_input = QLineEdit()
		self.url_input.setPlaceholderText("https://nexusmods.com/games/.../collections/.../")
		layout.addWidget(self.url_input)

		self.submit_btn = QPushButton("Submit")
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn) 

		self.setLayout(layout)

	def get_url(self):
		input = self.url_input.text().strip()
		input = input.replace("http://", "https://")
		for suffix in ["/mods", "/comments", "/changelog", "/bugs"]:
			if input.endswith(suffix):
				input = input[: -len(suffix)]
		qDebug(f"[NXMColDL] URL entered: {input}")
		var.uri = input
		return self.check_valid(input)

	def check_valid(self, url):
		regex = r"^https:\/\/www\.nexusmods\.com\/games\/([a-zA-Z0-9_\-]+)\/collections\/([a-zA-Z0-9_\-]+)\/?$"
		valid = re.match(regex, url)
		if valid:
			qDebug("[NXMColDL] URL is valid")
			return valid

	def submit(self):
		matched = self.get_url()
		if not matched: QMessageBox.critical(self, "Error", "The URL you entered is not a valid Nexus Collection URL."); return
		var.game = matched.group(1)
		qDebug(f"[NXMColDL] Game: {var.game}")
		var.collection = matched.group(2)
		qDebug(f"[NXMColDL] Collection ID: {var.collection}")
		self.close()
		stepVersion(self.parent()).exec()

class stepVersion(QDialog):
    
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("NXM Collection Downloader - Select Revision")
		self.setMinimumWidth(300)
    
		layout = QVBoxLayout()

		self.label = QLabel("Select Collection Revision:")
		layout.addWidget(self.label)

		self.dropdown = QComboBox()
		self.getList()
		layout.addWidget(self.dropdown)

		self.submit_btn = QPushButton("Submit")
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn)

		self.setLayout(layout)

	def getList(self):
		revisions = fetchRevisions(var.uri)
		if revisions: 
			for data in revisions["collection"]["revisions"]:
				self.dropdown.addItem(f"Revision {data['revisionNumber']} ({data["createdAt"].split("T")[0]})")
	
	def submit(self):
		revision_text = self.dropdown.currentText()
		var.revision = int(revision_text.replace('Revision ', '').split(' (')[0])
		qDebug(f"[NXMColDL] Selected Revision: {var.revision}")
		self.close()