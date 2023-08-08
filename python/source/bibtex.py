from __future__ import annotations

import logging

import requests


def from_doi(doi: str, pretty: bool, timeout: float) -> str:
    """Downloads and formats BibTeX from https://dx.doi.org/.

    Args:
        doi (str): Digital object identifier (DOI) string starting with ``10.``.
        pretty (bool): Whether to correct line breaks and indents.
            Otherwise, this function returns the raw reponse from https://dx.doi.org/.
        timeout (float): Request timeout in seconds.

    Raises:
        :py:class:`requests.exceptions.HTTPError`: if a network error occurs (unreachable server, timeout...).

    Returns:
        str: BibTeX entry for the given DOI.
    """
    logging.debug(f"request application/x-bibtex from https://dx.doi.org/{doi}")
    response = requests.get(
        f"https://dx.doi.org/{doi}",
        timeout=timeout,
        headers={"Accept": "application/x-bibtex; charset=utf-8"},
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
