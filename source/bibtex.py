import os
from . import certificates

certificates_bundle = certificates.bundle()
if certificates_bundle is not None:
    os.environ["REQUESTS_CA_BUNDLE"] = certificates_bundle
import requests


def from_doi(doi: str, pretty: bool, timeout: float) -> str:
    response = requests.get(
        f"https://dx.doi.org/{doi}", timeout=timeout, headers={"Accept": "application/x-bibtex; charset=utf-8"}
    )
    response.raise_for_status()
    if pretty:
        bibtex = ""
        new_line = True
        depth = 0
        for character in response.text:
            if new_line:
                if not character.isspace():
                    new_line = False
                    bibtex += " " * ((depth - 1 if character == "}" else depth) * 4)
            if character == "{":
                depth += 1
                bibtex += "{"
            elif character == "}":
                depth -= 1
                bibtex += "}"
            elif character == "\n":
                new_line = True
                bibtex += "\n"
            elif character.isspace():
                if not new_line:
                    bibtex += character
            else:
                bibtex += character
        if not bibtex.endswith("\n"):
            bibtex += "\n"
        return bibtex
    return response.text
