project = "UNDR"
copyright = "Alexandre Marcireau, ICNS"
author = "Alexandre Marcireau"

extensions = [
    "autoapi.extension",
    "myst_parser",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
intersphinx_mapping = {
    "numpy": ("https://numpy.org/doc/stable/", None),
    "python": ("https://docs.python.org/3", None),
    "requests": ("https://requests.readthedocs.io/en/latest/", None),
}

html_css_files = ["css/custom.css"]
html_theme = "furo"
html_static_path = ["_static"]

autoapi_add_toctree_entry = False
autoapi_dirs = ["../python/undr"]
autoapi_ignore = ["*__main__*"]
autoapi_keep_files = True
autoapi_member_order = "alphabetical"
autoapi_template_dir = "_templates/autoapi"
autoapi_type = "python"
