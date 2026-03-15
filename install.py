import json
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, qDebug
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from . import __meta__, var


class stepSelectCollection(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NXM Collection Installer - Select Collection")
        self.setMinimumWidth(400)

        self.collections_list = []
        self.current_metadata = None
        self.network_manager = None

        layout = QVBoxLayout()

        # Dropdown at the top
        self.label = QLabel("Select a downloaded collection to install:")
        layout.addWidget(self.label)

        self.dropdown = QComboBox()
        self.dropdown.currentIndexChanged.connect(self.on_selection_changed)
        layout.addWidget(self.dropdown)

        layout.addSpacing(10)

        # Info display section
        infoBox = QHBoxLayout()

        self.thumb_label = QLabel()
        self.thumb_label.setMaximumHeight(128)
        self.thumb_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        infoBox.addWidget(self.thumb_label)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        infoBox.addWidget(self.info)

        layout.addLayout(infoBox)

        layout.addSpacing(10)

        # Submit button
        self.submit_btn = QPushButton("Next")
        self.submit_btn.clicked.connect(self.submit)
        self.submit_btn.setEnabled(False)  # Disabled until a collection is loaded
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def showEvent(self, event):
        """Refresh collections list every time the dialog is shown"""
        super().showEvent(event)
        self.refreshCollections()

    def refreshCollections(self):
        """Reload and refresh the collections list"""
        # Clear current dropdown
        self.dropdown.blockSignals(True)
        self.dropdown.clear()
        self.collections_list = []
        self.current_metadata = None
        self.dropdown.blockSignals(False)

        # Load collections
        plugin_instance = getattr(__meta__, "_install_plugin", None)
        if not plugin_instance or not hasattr(plugin_instance, "_organizer"):
            QMessageBox.critical(self, "Error", "Failed to access Mod Organizer")
            qDebug("[NXMColDL] Failed to get plugin instance")
            self.close()
            return

        base_path = Path(plugin_instance._organizer.basePath())
        self.collections_list = var.listCollectionMetadata(base_path)

        if not self.collections_list:
            QMessageBox.information(
                self,
                "No Collections Found",
                "No downloaded collections found.\n\nPlease download a collection first using the Download Collection tool.",
            )
            qDebug("[NXMColDL] No collections found")
            self.close()
            return

        # Populate dropdown
        for game, collection_id, revision, metadata_file in self.collections_list:
            # Load metadata to get the display name
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    name = metadata.get("name", collection_id)
                    # author = metadata.get("author", "Unknown")
                    display_text = f"{name} (Rev {revision}) - {game}"
                    self.dropdown.addItem(display_text)
            except Exception as e:
                qDebug(f"[NXMColDL] Error loading metadata from {metadata_file}: {e}")
                self.dropdown.addItem(f"{collection_id} (Rev {revision}) - {game}")

        # Trigger initial selection
        if self.dropdown.count() > 0:
            self.on_selection_changed(0)

    def on_selection_changed(self, index):
        """Handle dropdown selection change"""
        if index < 0 or index >= len(self.collections_list):
            return

        game, collection_id, revision, metadata_file = self.collections_list[index]

        # Load metadata
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                self.current_metadata = json.load(f)

            # Update display
            name = self.current_metadata.get("name", "Unknown Collection")
            author = self.current_metadata.get("author", "Unknown Author")
            summary = self.current_metadata.get("summary", "No description available.")
            thumbnail = self.current_metadata.get("thumbnail")
            total_mods = self.current_metadata.get("totalMods", 0)
            timestamp = self.current_metadata.get("timestamp", "Unknown")

            # Clean up summary for display
            summary = (
                var.cleanJson(summary, True) if summary else "No description available."
            )

            # Update info label
            self.info.setText(f"""
				<h2 style="margin:0;padding:0">{name}</h2>
				<br>
				by <i>{author}</i>
				<br>
				<br>
				{summary}
				<br>
				<br>
				<b>Total Mods:</b> {total_mods}
				<br>
				<b>Downloaded:</b> {timestamp.split("T")[0] if "T" in timestamp else timestamp}
			""")

            # Update thumbnail
            if thumbnail:
                self.network_manager = var.loadThumbnail(
                    thumbnail, self.thumb_label, self.network_manager
                )
            else:
                self.thumb_label.clear()

            self.submit_btn.setEnabled(True)

            qDebug(f"[NXMColDL] Selected collection: {name} (Rev {revision})")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load collection metadata: {e}"
            )
            qDebug(f"[NXMColDL] Error loading metadata: {e}")
            self.submit_btn.setEnabled(False)

    def submit(self):
        """Proceed to next step with selected collection"""
        if not self.current_metadata:
            QMessageBox.critical(self, "Error", "No collection selected")
            return

        # Store metadata in var for use in subsequent steps
        var.uri = self.current_metadata.get("uri")
        var.game = self.current_metadata.get("game")
        var.collection = self.current_metadata.get("collection")
        var.revision = self.current_metadata.get("revision")
        var.author = self.current_metadata.get("author", "Unknown Author")
        var.name = self.current_metadata.get("name", "Unknown Collection")
        var.summary = self.current_metadata.get("summary", "No description available.")
        var.thumbnail = self.current_metadata.get("thumbnail")
        var.essentialMods = self.current_metadata.get("essentialMods", [])
        var.chosenOptional = self.current_metadata.get("chosenOptional", [])
        var.externalMods = self.current_metadata.get("externalMods", [])

        qDebug(f"[NXMColDL] Loaded collection: {var.name}")
        qDebug(f"[NXMColDL] Essential mods: {len(var.essentialMods)}")
        qDebug(f"[NXMColDL] Optional mods: {len(var.chosenOptional)}")

        self.close()

        # Proceed to installation step
        stepInstallMods(self.parent()).exec()


class stepInstallMods(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NXM Collection Installer - Installing Mods")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        # Title
        title = QLabel(f"Installing: {var.name}")
        title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        layout.addWidget(title)

        # Progress info
        self.progress_label = QLabel("Preparing installation...")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        layout.addWidget(self.progress_bar)

        # Log area
        log_label = QLabel("Installation Log:")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        layout.addWidget(self.log_text)

        # Close button (initially disabled)
        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)

        self.setLayout(layout)

        # Start installation after dialog is shown
        QTimer.singleShot(100, self.startInstallation)

    def log(self, message, level="info"):
        color = "black"
        if level == "error":
            color = "red"
        elif level == "warning":
            color = "orange"
        elif level == "success":
            color = "green"

        self.log_text.append(f'<span style="color: {color};">{message}</span>')
        qDebug(f"[NXMColDL Install] {message}")
        QApplication.processEvents()

    def startInstallation(self):
        """Main installation process"""
        try:
            plugin_instance = getattr(__meta__, "_install_plugin", None)
            if not plugin_instance or not hasattr(plugin_instance, "_organizer"):
                self.log("Failed to access Mod Organizer", "error")
                self.close_btn.setEnabled(True)
                return

            organizer = plugin_instance._organizer
            modlist = organizer.modList()

            # Get all mods to install in order
            mods_to_install = var.essentialMods + var.chosenOptional
            self.progress_bar.setMaximum(len(mods_to_install))

            self.log(f"Total mods to install: {len(mods_to_install)}")

            # Get initial mod count to determine starting priority
            # Collection mods will be placed at the end of the current mod list
            initial_mod_count = len(modlist.allMods())
            base_priority = initial_mod_count
            self.log(f"Existing mods in list: {initial_mod_count}")
            self.log(f"Collection mods will start at priority: {base_priority}")
            self.log("")

            # Find downloaded files
            downloads_path = Path(organizer.downloadsPath())
            self.log(f"Searching for downloads in: {downloads_path}")

            # Build a mapping of (modId, fileId) -> download_path
            download_map = self.buildDownloadMap(downloads_path)
            self.log(f"Found {len(download_map)} downloaded files")
            self.log("")

            # Install each mod in order
            installed_mods = []
            for idx, mod_info in enumerate(mods_to_install, 1):
                self.progress_label.setText(
                    f"Installing mod {idx}/{len(mods_to_install)}"
                )
                self.progress_bar.setValue(idx - 1)

                mod_id = mod_info["file"]["mod"]["modId"]
                file_id = mod_info["file"]["fileId"]
                mod_name = mod_info["file"]["mod"]["name"]
                file_name = mod_info["file"]["name"]

                self.log(f"[{idx}/{len(mods_to_install)}] Processing: {mod_name}")
                self.log(f"  File: {file_name} (ModID: {mod_id}, FileID: {file_id})")

                # Find downloaded file
                download_key = (int(mod_id), int(file_id))
                if download_key not in download_map:
                    self.log("  ERROR: Not found in downloads - skipping", "error")
                    self.log("")
                    continue

                download_path = download_map[download_key]
                self.log(f"  Found: {download_path.name}")

                # Install the mod
                try:
                    installed_mod = organizer.installMod(str(download_path), mod_name)
                    if installed_mod:
                        internal_name = installed_mod.name()
                        modlist.setActive(internal_name, True)
                        self.log(f"  Installed as: {internal_name}", "success")

                        # Set priority to maintain collection order
                        target_priority = base_priority + len(installed_mods)
                        if modlist.setPriority(internal_name, target_priority):
                            self.log(f"  Priority set to: {target_priority}", "success")
                        else:
                            self.log(
                                f"  WARNING: Failed to set priority to {target_priority}",
                                "warning",
                            )

                        installed_mods.append(internal_name)
                    else:
                        self.log(
                            "  ERROR: Installation failed or was cancelled", "error"
                        )
                except Exception as e:
                    self.log(f"  ERROR: Installation error: {e}", "error")

                self.log("")

            # Final summary
            self.progress_bar.setValue(len(mods_to_install))
            self.progress_label.setText("Installation complete!")
            self.log("=" * 50)
            self.log("Installation Summary:", "success")
            self.log(f"  Total mods: {len(mods_to_install)}")
            self.log(f"  Successfully installed: {len(installed_mods)}")
            self.log(f"  Failed/Skipped: {len(mods_to_install) - len(installed_mods)}")

            if len(installed_mods) < len(mods_to_install):
                self.log("", "warning")
                self.log(
                    "Some mods were not installed. Make sure all mods are downloaded first.",
                    "warning",
                )

        except Exception as e:
            self.log(f"Fatal error during installation: {e}", "error")
            import traceback

            self.log(traceback.format_exc(), "error")

        finally:
            self.close_btn.setEnabled(True)

    def buildDownloadMap(self, downloads_path: Path):
        download_map = {}

        if not downloads_path.exists():
            self.log(f"Downloads directory does not exist: {downloads_path}", "error")
            return download_map

        # Iterate through all .meta files in downloads directory
        for meta_file in downloads_path.glob("*.meta"):
            try:
                # The actual download file has the same name without .meta extension
                download_file = meta_file.with_suffix("")

                # Only consider files that exist and are not directories
                if not download_file.exists() or download_file.is_dir():
                    continue

                # Parse the .meta file (it's an INI-style file)
                mod_id = None
                file_id = None

                with open(meta_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("modID="):
                            mod_id = int(line.split("=", 1)[1])
                        elif line.startswith("fileID="):
                            file_id = int(line.split("=", 1)[1])

                        # Early exit if we found both
                        if mod_id is not None and file_id is not None:
                            break

                if mod_id is not None and file_id is not None:
                    download_map[(mod_id, file_id)] = download_file
                else:
                    qDebug(
                        f"[NXMColDL] Incomplete metadata in {meta_file.name}: modID={mod_id}, fileID={file_id}"
                    )

            except (ValueError, IOError) as e:
                qDebug(f"[NXMColDL] Error parsing {meta_file.name}: {e}")
            except Exception as e:
                qDebug(f"[NXMColDL] Unexpected error parsing {meta_file.name}: {e}")

        return download_map
