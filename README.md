<p align="center">
    <img src="https://raw.githubusercontent.com/neuromorphicsystems/undr/main/undr.png" width="256">
</p>

# Unified Neuromorphic Datasets Repository

- [Python package](#python-package)
- [Dataset format specification](#dataset-format-specification)
- [Dataset mirrors](#dataset-mirrors)

## Python package

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
