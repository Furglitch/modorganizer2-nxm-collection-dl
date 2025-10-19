import re
import json
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl

from .api import fetchRevisions, fetchInfo, fetchModInfo
from . import var


class ModInfoWorker(QObject):
	finished = pyqtSignal(object)
	error = pyqtSignal(str)

	def __init__(self, uri):
		super().__init__()
		self.uri = uri

	def run(self):
		try:
			mods = fetchModInfo(self.uri)
			if mods is None:
				self.error.emit('Failed to fetch mod info')
			else:
				self.finished.emit(mods)
		except Exception as e:
			self.error.emit(str(e))

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

		collectionData = fetchInfo(var.uri)

		qDebug(f"[NXMColDL] Collection Info: {var.cleanJson(collectionData)}")
		if collectionData:
			var.author = collectionData["collection"]["user"]["name"]
			var.name = collectionData["collection"]["name"]
			var.summary = var.cleanJson(collectionData["collection"]["summary"], True)
			var.thumbnail = collectionData["collection"].get("tileImage", {}).get("thumbnailUrl")
			qDebug(f"[NXMColDL] Collection Name: {var.name}")
			qDebug(f"[NXMColDL] Collection Author: {var.author}")
			qDebug(f"[NXMColDL] Collection Summary: {var.summary}")
			qDebug(f"[NXMColDL] Collection Thumbnail: {var.thumbnail}")
		
		infoBox = QHBoxLayout()

		self.thumb_label = QLabel()
		self.thumb_label.setMaximumHeight(128)
		self.thumb_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
		self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		if var.thumbnail:
			self.getThumb()
			infoBox.addWidget(self.thumb_label)

		self.info = QLabel(f"""
							<h2 style="margin:0;padding:0">{var.name}</h2>
							<br>
							by <i>{var.author}</i>
							<br>
							<br>
							{var.summary}
							""")
		self.info.setWordWrap(True)
		infoBox.addWidget(self.info)

		layout.addLayout(infoBox)

		layout.addSpacing(10)

		self.label = QLabel("Select Revision:")
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
			for data in revisions.get("collection", {}).get("revisions", []):
				created = data.get("createdAt", "").split("T")[0] if data.get("createdAt") else ""
				self.dropdown.addItem(f'Revision {data.get("revisionNumber", "?")} ({created})')
	
	def getThumb(self):
		manager = QNetworkAccessManager(self)
		def handle_reply(reply: QNetworkReply):
			if reply.error() == QNetworkReply.NetworkError.NoError:
				data = reply.readAll()
				pix = QPixmap()
				if pix.loadFromData(data):
					pix = pix.scaledToHeight(128, Qt.TransformationMode.SmoothTransformation)
					self.thumb_label.setPixmap(pix)
					qDebug("[NXMColDL] Thumbnail loaded")
				else:
					qDebug("[NXMColDL] Failed to load thumbnail data into QPixmap")
			else:
				qDebug(f"[NXMColDL] Network error loading thumbnail: {reply.errorString()}")
			reply.deleteLater()
		# make request
		request = QNetworkRequest(QUrl(var.thumbnail))
		reply = manager.get(request)
		reply.finished.connect(lambda r=reply: handle_reply(r))

	def submit(self):
		revision_text = self.dropdown.currentText()
		var.revision = int(revision_text.replace('Revision ', '').split(' (')[0])
		qDebug(f"[NXMColDL] Selected Revision: {var.revision}")
		self.close()
		stepModCount(self.parent()).exec()

class stepModCount(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("NXM Collection Downloader - Mod Count")
		self.setMinimumWidth(300)

		layout = QVBoxLayout()
		label = QLabel("This collection contains the following:")
		layout.addWidget(label)

		self.essentialLabel = QLabel("Loading essential mods...")
		self.optionalLabel = QLabel("Loading optional mods...")
		self.externalLabel = QLabel("Loading external resources...")
		self.bundledLabel = QLabel("Loading bundled resources...")

		layout.addWidget(self.essentialLabel)
		layout.addWidget(self.optionalLabel)
		layout.addWidget(self.externalLabel)
		layout.addWidget(self.bundledLabel)

		self.submit_btn = QPushButton("Next")
		self.submit_btn.setEnabled(False) # disabled until data is loaded
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn)

		self.setLayout(layout)

		self.getMods()

	def getMods(self):
		var.essentialMods.clear()
		var.optionalMods.clear()
		var.chosenOptional.clear()
		var.externalMods.clear()
		var.bundledMods.clear()

		# background process for loading modlist
		self._thread = QThread(self)
		self._worker = ModInfoWorker(var.uri)
		self._worker.moveToThread(self._thread)
		self._thread.started.connect(self._worker.run)
		self._worker.finished.connect(self._on_mods_fetched)
		self._worker.error.connect(self._on_mods_error)
		self._worker.finished.connect(self._thread.quit)
		self._worker.finished.connect(self._worker.deleteLater)
		self._thread.finished.connect(self._thread.deleteLater)
		self._thread.start()


	def _on_mods_error(self, err):
		qDebug(f"[NXMColDL] Error fetching mods: {err}")
		QMessageBox.critical(self, "Error", f"Failed to load mod information: {err}")
		self.essentialLabel.setText("Error loading essential mods")
		self.optionalLabel.setText("Error loading optional mods")
		self.externalLabel.setText("Error loading external resources")
		self.bundledLabel.setText("Error loading bundled resources")


	def _on_mods_fetched(self, mods):
		qDebug(f"[NXMColDL] Mods Info: {var.cleanJson(mods)}")
		for mod in mods.get("collectionRevision", {}).get("modFiles", []):
			if not mod.get("optional"):
				var.essentialMods.append(mod)
				qDebug(f"[NXMColDL] Essential mod added: {mod['file']['mod']['name']}")
			else:
				var.optionalMods.append(mod)
				qDebug(f"[NXMColDL] Optional mod added: {mod['file']['mod']['name']}")
		for mod in mods.get("collectionRevision", {}).get("externalResources", []):
			if mod.get("resourceUrl"):
				var.externalMods.append(mod)
				qDebug(f"[NXMColDL] External resource added: {mod.get('name')}")
			else:
				var.bundledMods.append(mod)
				qDebug(f"[NXMColDL] Bundled resource added: {mod.get('name')}")

		essentialCount = len(var.essentialMods)
		optionalCount = len(var.optionalMods)
		externalCount = len(var.externalMods)
		bundledCount = len(var.bundledMods)

		self.essentialLabel.setText(f"{essentialCount} essential mods")
		self.optionalLabel.setText(f"{optionalCount} optional mods")
		self.externalLabel.setText(f"{externalCount} external resources")
		self.bundledLabel.setText(f"{bundledCount} bundled resources")

		self.submit_btn.setEnabled(True)

	def submit(self):
		self.close()
		if var.essentialMods:
			stepEssential(self.parent()).exec()
		elif var.optionalMods:
			stepOptional(self.parent()).exec()
		elif var.externalMods:
			stepExternal(self.parent()).exec()
		elif var.bundledMods:
			stepBundled(self.parent()).exec()
		else:
			stepSummary(self.parent()).exec()

class stepEssential(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("NXM Collection Downloader - Essential Mods")
		self.setMinimumWidth(300)

		layout = QVBoxLayout()
		label = QLabel("Included 'Essential' mods:")
		layout.addWidget(label)

		self.modlist = QListWidget()
		self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
		self.modlist.setAlternatingRowColors(True)
		for mod in var.essentialMods:
			item_text = f"Mod: {mod['file']['mod']['name']}\nFile: {mod['file']['name']} - {mod['file']['version']}\nby {mod['file']['mod']['author']}"
			item = QListWidgetItem(item_text)
			item.setData(Qt.ItemDataRole.UserRole, mod)
			self.modlist.addItem(item)
		self.modlist.setMinimumHeight(200)
		layout.addWidget(self.modlist)

		self.submit_btn = QPushButton("Next")
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn)

		self.setLayout(layout)

	def submit(self):
		self.close()
		if var.optionalMods:
			stepOptional(self.parent()).exec()
		elif var.externalMods:
			stepExternal(self.parent()).exec()
		elif var.bundledMods:
			stepBundled(self.parent()).exec()
		else:
			stepSummary(self.parent()).exec()

class stepOptional(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("NXM Collection Downloader - Optional Mods")
		self.setMinimumWidth(300)

		layout = QVBoxLayout()
		label = QLabel("Select 'Optional' mods:")
		layout.addWidget(label)

		self.modlist = QListWidget()
		self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
		self.modlist.setAlternatingRowColors(True)
		for mod in var.optionalMods:
			item_text = f"Mod: {mod['file']['mod']['name']}\nFile: {mod['file']['name']} - {mod['file']['version']}\nby {mod['file']['mod']['author']}"
			item = QListWidgetItem(item_text)
			item.setData(Qt.ItemDataRole.UserRole, mod)
			item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
			item.setCheckState(Qt.CheckState.Checked)
			item.setSizeHint(QSize(0, QFontMetrics(self.modlist.font()).lineSpacing() * 3 + 8))
			self.modlist.addItem(item)
		self.modlist.setMinimumHeight(200)
		layout.addWidget(self.modlist)

		self.submit_btn = QPushButton("Next")
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn)

		self.setLayout(layout)

	def submit(self):

		var.chosenOptional = []
		for i in range(self.modlist.count()):
			item = self.modlist.item(i)
			if item.checkState() == Qt.CheckState.Checked:
				mod_data = item.data(Qt.ItemDataRole.UserRole)
				var.chosenOptional.append(mod_data)
				qDebug(f"[NXMColDL] Optional mod selected: {mod_data['file']['mod']['name']}")
		
		qDebug(f"[NXMColDL] Total optional mods selected: {len(var.chosenOptional)}")
		
		self.close()
		if var.externalMods:
			stepExternal(self.parent()).exec()
		elif var.bundledMods:
			stepBundled(self.parent()).exec()
		else:
			stepSummary(self.parent()).exec()

class stepExternal(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("NXM Collection Downloader - External Mods")
		self.setMinimumWidth(300)

		layout = QVBoxLayout()
		label = QLabel("Included 'External' mods:")
		layout.addWidget(label)

		self.modlist = QListWidget()
		self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
		self.modlist.setAlternatingRowColors(True)
		for mod in var.externalMods:
			item = QListWidgetItem(f"{mod['name']}")
			item.setData(Qt.ItemDataRole.UserRole, mod)
			self.modlist.addItem(item)
		self.modlist.setMinimumHeight(200)
		layout.addWidget(self.modlist)

		self.urlCheck = QCheckBox("Open URLs in Browser")
		self.urlCheck.setChecked(True)
		self.urlCheck.stateChanged.connect(lambda s: setattr(var, "chosenExternal", bool(s)))
		layout.addWidget(self.urlCheck)

		self.submit_btn = QPushButton("Next")
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn)

		self.setLayout(layout)

	def submit(self):
		self.close()
		if not var.chosenExternal:
			var.externalMods.clear() # clear if not chosen
		if var.bundledMods:
			stepBundled(self.parent()).exec()
		else:
			stepSummary(self.parent()).exec()

class stepBundled(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("NXM Collection Downloader - Bundled Mods")
		self.setMinimumWidth(300)

		layout = QVBoxLayout()
		label = QLabel("Included 'Bundled' mods:")
		layout.addWidget(label)

		self.modlist = QListWidget()
		self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
		self.modlist.setAlternatingRowColors(True)
		for mod in var.bundledMods:
			item = QListWidgetItem(f"{mod['file']['mod']['name']} by {mod['file']['mod']['author']}")
			item.setData(Qt.ItemDataRole.UserRole, mod)
			self.modlist.addItem(item)
		self.modlist.setMinimumHeight(200)
		layout.addWidget(self.modlist)

		self.submit_btn = QPushButton("Next")
		self.submit_btn.clicked.connect(self.submit)
		layout.addWidget(self.submit_btn)

		self.setLayout(layout)

	def submit(self):
		self.close()
		#stepOptional(self.parent()).exec()