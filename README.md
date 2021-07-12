<p align="center">
    <img src="https://raw.githubusercontent.com/neuromorphicsystems/undr/main/undr.png" width="256">
</p>

# Unified Neuromorphic Datasets Repository

- [Getting started](#getting-started)
  - [Install the undr module](#install-the-undr-module)
  - [Generate a default configuration file](#generate-a-default-configuration-file)
  - [Download the datasets](#download-the-datasets)
  - [Process the data](#process-the-data)
  - [Generate a BibTex file](#generate-a-bibtex-file)
- [Python module](#python-module)
- [Dataset format specification](#dataset-format-specification)
- [Dataset mirrors](#dataset-mirrors)

## Getting Started

### Install the undr module

```sh
pip3 install undr
```

### Generate a default configuration file

```sh
python3 -m undr init
```

The generated *undr.toml* file is written in TOML (https://github.com/toml-lang/toml). It lists the datasets that will be downloaded or streamed, hence it needs to be ajusted to your needs.

The line `directory = 'datasets'` specifies the directory where downloaded files are stored (relatively to the configuration file). All the files generated by `undr` (directory indexes, downloaded data, temporary files...) are stored in this directory.

Datasets are listed as `[[datasets]]` entries with three mandatory properties: `name`, `url` and `mode`. The optional `server_type` property is used internally to speed up the download process. To discard a dataset, you can either remove it from the configuration file or comment all its lines with `#` signs.

`mode` changes the download strategy on a per-dataset basis, with three possible values:
- `'remote'` only downloads the dataset's file index. The `undr` Python package can be used to process the dataset files as if they were on your hard drive by streaming them from the server. This option is particularly useful for large datasets that do not fit on your disk but requires a fast internet connection since files are re-downloaded every time they are processed.
- `'local'` downloads all the dataset files locally but does not decompress them (most datasets are stored as [lzip](https://www.nongnu.org/lzip/) archives). The `undr` Python library transparently decompresses files in memory when you read them, making this option a good trade-off between disk usage and processing speed.
- `'local-decompressed'` downloads all the dataset files locally and decompresses them. Decompressed files use a relatively inefficient plain binary file format so this option requires vast amounts of disk space (3 to 5 times as much as the lzip archives). On the other hand, the plain binary format facilitates processing with other languages such as Matlab or C++.

`undr` also supports hybrid configurations where only part of a dataset is downloaded or decompressed. You may also use local directories without a server. See [NOT DOCUMENTED YET] for details.

### Download the datasets

```sh
python3 -m undr install
```

This command downloads the datasets file indexes. If the `mode` is `'compressed'` or `'decompress'`, it also downloads the dataset files (and possibly decompresses them).

This command can be interrupted at any time with CTRL + C. Re-running it will resume download where it left off.

### Generate a BibTex file

```sh
python3 -m undr bibtex --output datasets.bib
```

The UNDR project does not claim authorship of the datasets. Please use this file to cite the origiinal articles.

## Python module

```sh
pip3 install undr
```

## Dataset format specification

`-index`: '-' comes before alpha-numeric characters in ASCII, not reserved in URLs/bash/filesystems

## Dataset mirrors

### Example configuration

#### Apache

```xml
<VirtualHost *:80>
    Alias / /path/to/local/directory/
    <Directory "/path/to/local/directory/">
        Require all granted
        Options +Indexes
    </Directory>
</VirtualHost>
```

To use another port, remember to edit */etc/apache2/ports.conf* as well.

#### Nginx

```nginx
server {
    listen 80;
    location / {
        alias /path/to/local/directory/;
        autoindex on;
        sendfile on;
        tcp_nopush on;
        sendfile_max_chunk 1m;
    }
}
```

## Publish

1. Bump the version number in *setup.py*.

2. Install twine
```
pip3 install twine
```

3. Upload the source code to PyPI:
```
rm -rf dist
python3 setup.py sdist
python3 -m twine upload dist/*
```
