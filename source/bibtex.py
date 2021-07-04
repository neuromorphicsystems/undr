import os
from . import certificates

certificates_bundle = certificates.bundle()
if certificates_bundle is not None:
    os.environ["REQUESTS_CA_BUNDLE"] = certificates_bundle
import requests


def from_doi(doi: str, pretty: bool) -> str:
    response = requests.get(f"https://dx.doi.org/{doi}", headers={"Accept": "text/bibliography; style=bibtex"})
    if pretty:
        bibtex = ""
        depth = 0
        for character in response.text:
            if character == "{":
                depth += 1
                bibtext += "{"
            elif character == "}":
                depth -= 1
                if depth == 0:
                    bibtex += ",\n}"
                else:
                    bibtext += "}"
            elif character == ",":
                if depth < 2:
                    bibtex += ",\n   "
                else:
                    bibtex += ","
            elif character == "%":
                bibtex += "\\%"
            else:
                bibtex += character
        return bibtex
    return response.text
