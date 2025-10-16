import json
import urllib.request
from PyQt6.QtCore import qDebug

from . import var

def nxmFetch(requestData):
    jsonData = json.dumps(requestData).encode("utf-8")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20211714 Firefox/135.0",
        "Accept": "application/json",
        "Content-type": "application/json",
    }
    request = urllib.request.Request("https://api.nexusmods.com/v2/graphql", data=jsonData, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            content = response.read()
            resp = json.loads(content)
            qDebug(var.cleanJson(resp))
            return resp.get("data")
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        qDebug(f"[NXMColDL] Error fetching data: {str(e)}")
        return None
    
def fetchRevisions(url):
    qDebug(f"[NXMColDL] Fetching revisions for {url}")
    query = """
            query CollectionRevisions($domainName: String, $slug: String!) {
                collection(domainName: $domainName, slug: $slug) {
                    revisions {
                        createdAt
                        revisionNumber
                    }
                }
            }
            """
    jsonData = {
        "query": query,
        "variables": {
            "domainName": var.game,
            "slug": var.collection
        },
        "operationName": "CollectionRevisions"
    }
    return nxmFetch(jsonData)

def fetchInfo(url):
    qDebug(f"[NXMColDL] Fetching collection info for {url}")
    query = """
            query CollectionManifestInfo($domainName: String, $slug: String!) {
                collection(domainName: $domainName, slug: $slug) {
                    name
                    summary
                    user {
                        name
                    }
                    tileImage {
                        thumbnailUrl(size: small)
                    }
                }
            }
            """
    jsonData = {
        "query": query,
        "variables": {
            "domainName": var.game,
            "slug": var.collection
        },
        "operationName": "CollectionManifestInfo"
    }
    return nxmFetch(jsonData)

def fetchModInfo(url):
    qDebug(f"[NXMColDL] Fetching collection info for {url}")
    query = """
            query CollectionRevisionMods($revision: Int, $slug: String!, $viewAdultContent: Boolean) {
                collectionRevision(revision: $revision, slug: $slug, viewAdultContent: $viewAdultContent) {
                    externalResources {
                        id
                        name
                        resourceType
                        resourceUrl
                    }
                    modFiles {
                        fileId
                        optional
                        file {
                            fileId
                            name
                            scanned
                            size
                            sizeInBytes
                            version
                            mod {
                                adult
                                author
                                category
                                modId
                                name
                                pictureUrl
                                summary
                                version
                                game {
                                    domainName
                                }
                                uploader {
                                    avatar
                                    memberId
                                    name
                                }
                            }
                        }
                    }
                }
            }
            """
    jsonData = {
        "query": query,
        "variables": {
            "revision": var.revision,
            "slug": var.collection,
            "viewAdultContent": True,
        },
        "operationName": "CollectionRevisionMods"
    }
    return nxmFetch(jsonData)