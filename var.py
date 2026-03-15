import json
import re
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import qDebug, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

uri = None
game = None
collection = None
revision = None
author = "Unknown Author"
name = "Unknown Collection"
summary = "No description available."
thumbnail = None

essentialMods = []
optionalMods = []
externalMods = []
bundledMods = []

chosenOptional = []
chosenExternal = True
openModWebsites = False


def cleanJson(data, visible=False):
    data = json.dumps(data, ensure_ascii=True)
    if visible:
        data = re.sub(r"\\u[0-9a-fA-F]{4}", "", data)
    return data


def loadThumbnail(thumbnail_url, thumb_label, network_manager=None):
    if network_manager is None:
        network_manager = QNetworkAccessManager()

    def handle_reply(reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pix = QPixmap()
            if pix.loadFromData(data):
                pix = pix.scaledToHeight(
                    128, Qt.TransformationMode.SmoothTransformation
                )
                thumb_label.setPixmap(pix)
                qDebug("[NXMColDL] Thumbnail loaded")
            else:
                qDebug("[NXMColDL] Failed to load thumbnail data into QPixmap")
        else:
            qDebug(f"[NXMColDL] Network error loading thumbnail: {reply.errorString()}")
        reply.deleteLater()

    request = QNetworkRequest(QUrl(thumbnail_url))
    reply = network_manager.get(request)
    reply.finished.connect(lambda r=reply: handle_reply(r))

    return network_manager


def saveCollectionMetadata(base_path: Path):
    if not all([game, collection, revision]):
        missing = []
        if not game:
            missing.append("game")
        if not collection:
            missing.append("collection")
        if not revision:
            missing.append("revision")
        raise ValueError(
            f"Missing required collection information: {', '.join(missing)}"
        )

    # Create collections directory structure: <base>/collections/<game>/
    collections_dir = base_path / "collections" / game
    collections_dir.mkdir(parents=True, exist_ok=True)

    # Create metadata file path: <collection>_<revision>.json
    metadata_file = collections_dir / f"{collection}_{revision}.json"

    # Prepare metadata
    metadata = {
        "uri": uri,
        "game": game,
        "collection": collection,
        "revision": revision,
        "author": author,
        "name": name,
        "summary": summary,
        "thumbnail": thumbnail,
        "essentialMods": essentialMods,
        "chosenOptional": chosenOptional,
        "externalMods": externalMods,
        "timestamp": datetime.now().isoformat(),
        "totalMods": len(essentialMods) + len(chosenOptional),
    }

    # Save to file
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata_file


def loadCollectionMetadata(
    base_path: Path, game_name: str, collection_id: str, revision_num: int
):
    metadata_file = (
        base_path / "collections" / game_name / f"{collection_id}_{revision_num}.json"
    )

    if not metadata_file.exists():
        return None

    with open(metadata_file, "r", encoding="utf-8") as f:
        return json.load(f)


def listCollectionMetadata(base_path: Path):
    collections_dir = base_path / "collections"
    if not collections_dir.exists():
        return []

    collections = []
    for game_dir in collections_dir.iterdir():
        if game_dir.is_dir():
            for metadata_file in game_dir.glob("*.json"):
                try:
                    name_parts = metadata_file.stem.split("_")
                    if len(name_parts) >= 2:
                        collection_id = "_".join(name_parts[:-1])
                        revision_num = name_parts[-1]
                        collections.append(
                            (game_dir.name, collection_id, revision_num, metadata_file)
                        )
                except Exception as e:
                    qDebug(
                        f"[NXMColDL] Failed to parse collection metadata file '{metadata_file}': {e}"
                    )
                    continue

    return collections
