import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
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

qDebug = var.debug

MO2_WARNING_PATTERNS = (
    "Plugin not found:",
    "invalid origin name:",
    "[fomodinstallerdialog.cpp:",
)

EXPECTED_INSTALL_EXCEPTION_PATTERNS = (
    "invalid origin name:",
    "Plugin not found:",
)


def clickButtonByText(widget, texts):
    wanted = {text.lower() for text in texts}
    for button in widget.findChildren(QPushButton):
        label = button.text().replace("&", "").strip().lower()
        if label in wanted and button.isEnabled():
            suppressDialogAndClick(widget, button)
            return True
    return False


def suppressDialogAndClick(widget, button):
    widget.setUpdatesEnabled(False)
    widget.hide()
    QApplication.processEvents()
    button.click()


def acceptQuickInstallDialog():
    for widget in QApplication.topLevelWidgets():
        if not widget.isVisible() or widget.windowTitle() != "Quick Install":
            continue

        for button_box in widget.findChildren(QDialogButtonBox):
            button = button_box.button(QDialogButtonBox.StandardButton.Ok)
            if button and button.isEnabled():
                qDebug("[NXMColDL Install] Auto-accepting Quick Install dialog")
                suppressDialogAndClick(widget, button)
                return

        for button in widget.findChildren(QPushButton):
            if button.text().replace("&", "").lower() == "ok" and button.isEnabled():
                qDebug("[NXMColDL Install] Auto-accepting Quick Install dialog")
                suppressDialogAndClick(widget, button)
                return


def dismissKnownPostInstallErrorDialog(remaining=20):
    if remaining <= 0:
        return

    for widget in QApplication.topLevelWidgets():
        if not widget.isVisible() or widget.windowTitle() != "Error":
            continue

        labels = widget.findChildren(QLabel)
        if not any(
            "invalid origin name:" in label.text()
            or "Plugin not found:" in label.text()
            for label in labels
        ):
            continue

        for button_box in widget.findChildren(QDialogButtonBox):
            button = button_box.button(QDialogButtonBox.StandardButton.Ok)
            if button and button.isEnabled():
                qDebug("[NXMColDL Install] Dismissing known post-install error dialog")
                suppressDialogAndClick(widget, button)
                return

        for button in widget.findChildren(QPushButton):
            if button.text().replace("&", "").lower() == "ok" and button.isEnabled():
                qDebug("[NXMColDL Install] Dismissing known post-install error dialog")
                suppressDialogAndClick(widget, button)
                return

    QTimer.singleShot(250, lambda: dismissKnownPostInstallErrorDialog(remaining - 1))


def acceptModExistsDialog():
    for widget in QApplication.topLevelWidgets():
        if not widget.isVisible() or widget.windowTitle() != "Mod Exists":
            continue

        if clickButtonByText(widget, ("Merge",)):
            qDebug("[NXMColDL Install] Auto-merging Mod Exists dialog")
            return


def acceptDefaultInstallerDialog(remaining=80):
    if remaining <= 0:
        return

    for widget in QApplication.topLevelWidgets():
        if not widget.isVisible():
            continue

        title = widget.windowTitle()
        if title in ("Error", "Quick Install") or title.startswith(
            "NXM Collection Installer"
        ):
            continue

        buttons = widget.findChildren(QPushButton)
        button_by_text = {
            button.text().replace("&", "").strip().lower(): button for button in buttons
        }

        # MO2 installer/FOMOD dialogs expose Next/Install buttons. Accept the
        # already selected defaults, but do not click unrelated ordinary dialogs.
        next_button = button_by_text.get("next")
        install_button = button_by_text.get("install")
        if next_button and next_button.isEnabled():
            qDebug(f"[NXMColDL Install] Auto-accepting default installer page: {title}")
            suppressDialogAndClick(widget, next_button)
            QTimer.singleShot(300, lambda: acceptDefaultInstallerDialog(remaining - 1))
            return

        if install_button and install_button.isEnabled():
            qDebug(
                f"[NXMColDL Install] Auto-accepting default installer install: {title}"
            )
            suppressDialogAndClick(widget, install_button)
            QTimer.singleShot(300, lambda: acceptDefaultInstallerDialog(remaining - 1))
            return

    QTimer.singleShot(300, lambda: acceptDefaultInstallerDialog(remaining - 1))


def scheduleInstallDialogHandlers(
    auto_accept_quick_install=True,
    auto_dismiss_known_post_install_errors=True,
    auto_accept_fomod_defaults=False,
    auto_merge_existing_mods=True,
):
    for delay in (250, 750, 1500, 3000, 5000):
        if auto_accept_quick_install:
            QTimer.singleShot(delay, acceptQuickInstallDialog)
        if auto_dismiss_known_post_install_errors:
            QTimer.singleShot(delay, dismissKnownPostInstallErrorDialog)
        if auto_merge_existing_mods:
            QTimer.singleShot(delay, acceptModExistsDialog)
    if auto_accept_fomod_defaults:
        QTimer.singleShot(250, acceptDefaultInstallerDialog)


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
        qDebug(
            f"[NXMColDL] Found {len(self.collections_list)} collection(s) to install"
        )

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
        self.install_warnings = []

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

    def logInstallIssue(self, message, expected=False):
        """Log install issues without making expected MO2 chatter look fatal."""
        prefix = "NOTE" if expected else "ERROR"
        level = "warning" if expected else "error"
        self.log(f"  {prefix}: {message}", level)

    def isExpectedInstallException(self, error):
        message = str(error)
        return any(
            pattern in message for pattern in EXPECTED_INSTALL_EXCEPTION_PATTERNS
        )

    def interfaceLogPath(self, organizer):
        return Path(organizer.downloadsPath()).parent / "logs" / "mo_interface.log"

    def captureInterfaceLogPosition(self, organizer):
        log_path = self.interfaceLogPath(organizer)
        try:
            return log_path, log_path.stat().st_size
        except OSError:
            return log_path, 0

    def collectInterfaceLogWarnings(self, log_path, offset, mod_name, file_name):
        captured = 0
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
                log_file.seek(offset)
                for line in log_file:
                    line = line.rstrip()
                    if not any(pattern in line for pattern in MO2_WARNING_PATTERNS):
                        continue
                    warning = {
                        "mod": mod_name,
                        "file": file_name,
                        "message": line,
                    }
                    self.install_warnings.append(warning)
                    captured += 1
        except OSError as e:
            qDebug(f"[NXMColDL Install] Could not read MO2 interface log: {e}")
        return captured

    def writeWarningReport(self, organizer):
        if not self.install_warnings:
            return None

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_path = (
            self.interfaceLogPath(organizer).parent
            / f"nxm-collection-install-warnings-{var.collection}-{var.revision}-{timestamp}.json"
        )
        report = {
            "collection": var.collection,
            "revision": var.revision,
            "name": var.name,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "warning_count": len(self.install_warnings),
            "warnings": self.install_warnings,
        }
        with open(report_path, "w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2)
        return report_path

    def startInstallation(self):
        """Main installation process"""
        qDebug(f"[NXMColDL] Starting installation: {var.name}")
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

            installed_map = self.buildInstalledMap(Path(organizer.modsPath()))
            self.log(f"Found {len(installed_map)} installed Nexus file records")
            self.log("")

            # Install each mod in order
            installed_mods = []
            mods_to_activate = []
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

                install_key = (int(mod_id), int(file_id))
                if install_key in installed_map:
                    internal_name = installed_map[install_key]
                    self.log(f"  Already installed as: {internal_name}", "success")
                    self.log("")
                    installed_mods.append(internal_name)
                    activate_after_install = organizer.pluginSetting(
                        plugin_instance.name(), "activate_mods_after_install"
                    )
                    if activate_after_install:
                        mods_to_activate.append(internal_name)
                    continue

                # Find downloaded file
                if install_key not in download_map:
                    self.logInstallIssue("Not found in downloads - skipping")
                    self.log("")
                    continue

                download_path = download_map[install_key]
                self.log(f"  Found: {download_path.name}")

                # Install the mod
                log_path, log_offset = self.captureInterfaceLogPosition(organizer)
                try:
                    auto_accept_quick_install = organizer.pluginSetting(
                        plugin_instance.name(), "auto_accept_quick_install"
                    )
                    auto_dismiss_known_post_install_errors = organizer.pluginSetting(
                        plugin_instance.name(),
                        "auto_dismiss_known_post_install_errors",
                    )
                    auto_accept_fomod_defaults = organizer.pluginSetting(
                        plugin_instance.name(), "auto_accept_fomod_defaults"
                    )
                    auto_merge_existing_mods = organizer.pluginSetting(
                        plugin_instance.name(), "auto_merge_existing_mods"
                    )
                    activate_after_install = organizer.pluginSetting(
                        plugin_instance.name(), "activate_mods_after_install"
                    )
                    scheduleInstallDialogHandlers(
                        auto_accept_quick_install,
                        auto_dismiss_known_post_install_errors,
                        auto_accept_fomod_defaults,
                        auto_merge_existing_mods,
                    )

                    installed_mod = organizer.installMod(str(download_path))
                    warning_count = self.collectInterfaceLogWarnings(
                        log_path, log_offset, mod_name, file_name
                    )
                    if warning_count:
                        self.log(
                            f"  Captured {warning_count} MO2 warning(s) for report",
                            "warning",
                        )
                    if installed_mod:
                        internal_name = installed_mod.name()
                        self.log(f"  Installed as: {internal_name}", "success")

                        self.log(
                            "  Priority unchanged; MO2 appended the mod to the list",
                            "warning",
                        )

                        installed_mods.append(internal_name)
                        if activate_after_install:
                            mods_to_activate.append(internal_name)
                    else:
                        self.logInstallIssue(
                            "Installation failed or was cancelled", expected=True
                        )
                except Exception as e:
                    warning_count = self.collectInterfaceLogWarnings(
                        log_path, log_offset, mod_name, file_name
                    )
                    if warning_count:
                        self.log(
                            f"  Captured {warning_count} MO2 warning(s) for report",
                            "warning",
                        )
                    self.logInstallIssue(
                        f"Installation issue: {e}",
                        expected=self.isExpectedInstallException(e),
                    )

                self.log("")

            if mods_to_activate:
                self.progress_label.setText("Activating installed mods...")
                self.log(f"Activating {len(mods_to_activate)} installed mods...")
                log_path, log_offset = self.captureInterfaceLogPosition(organizer)
                for internal_name in mods_to_activate:
                    try:
                        modlist.setActive(internal_name, True)
                    except Exception as e:
                        self.logInstallIssue(f"Could not activate {internal_name}: {e}")
                warning_count = self.collectInterfaceLogWarnings(
                    log_path, log_offset, "post-install activation", ""
                )
                if warning_count:
                    self.log(
                        f"  Captured {warning_count} MO2 warning(s) during activation",
                        "warning",
                    )
                self.log("")

            # Final summary
            self.progress_bar.setValue(len(mods_to_install))
            self.progress_label.setText("Installation complete!")
            self.log("=" * 50)
            self.log("Installation Summary:", "success")
            self.log(f"  Total mods: {len(mods_to_install)}")
            self.log(f"  Successfully installed: {len(installed_mods)}")
            self.log(f"  Failed/Skipped: {len(mods_to_install) - len(installed_mods)}")
            self.log(f"  MO2 warnings captured: {len(self.install_warnings)}")
            report_path = self.writeWarningReport(organizer)
            if report_path:
                self.log(f"  Warning report: {report_path}", "warning")
            qDebug(
                f"[NXMColDL] Installation complete: {len(installed_mods)}/{len(mods_to_install)} succeeded"
            )

            if len(installed_mods) < len(mods_to_install):
                self.log("", "warning")
                self.log(
                    "Some mods were not installed. Make sure all mods are downloaded first.",
                    "warning",
                )

        except Exception as e:
            self.log(f"Fatal error during installation: {e}", "error")
        finally:
            self.close_btn.setEnabled(True)

    def buildDownloadMap(self, downloads_path: Path):
        download_map = {}

        if not downloads_path.exists():
            self.log(f"Downloads directory does not exist: {downloads_path}", "error")
            qDebug(f"[NXMColDL] Downloads path not found: {downloads_path}")
            return download_map

        qDebug(f"[NXMColDL] Building download map from: {downloads_path}")
        # Iterate through all .meta files in downloads directory
        for meta_file in downloads_path.glob("*.meta"):
            try:
                # The actual download file has the same name without .meta extension
                download_file = meta_file.with_suffix("")

                # Only consider files that exist and are not directories
                if not download_file.exists() or download_file.is_dir():
                    continue
                if download_file.name.endswith(".unfinished"):
                    qDebug(
                        f"[NXMColDL] Skipping unfinished download: {download_file.name}"
                    )
                    continue
                if download_file.stat().st_size == 0:
                    qDebug(f"[NXMColDL] Skipping empty download: {download_file.name}")
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

    def buildInstalledMap(self, mods_path: Path):
        installed_map = {}

        if not mods_path.exists():
            qDebug(f"[NXMColDL] Mods path not found: {mods_path}")
            return installed_map

        for meta_file in mods_path.glob("*/meta.ini"):
            mod_id = None
            file_ids = []
            try:
                with open(meta_file, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("modid="):
                            mod_id = int(line.split("=", 1)[1])
                        elif "\\fileid=" in line:
                            file_ids.append(int(line.split("=", 1)[1]))

                if mod_id is None:
                    continue

                for file_id in file_ids:
                    installed_map[(mod_id, file_id)] = meta_file.parent.name

            except (ValueError, IOError) as e:
                qDebug(f"[NXMColDL] Error parsing installed metadata {meta_file}: {e}")

        return installed_map
