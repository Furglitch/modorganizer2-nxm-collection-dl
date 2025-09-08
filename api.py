import json
import urllib.request
import logging

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
            logging.warning(resp)
            return resp.get("data")
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None