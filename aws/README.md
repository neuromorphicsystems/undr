-   [Develop](#develop)
-   [Deploy](#deploy)
-   [URL](#url)
    -   [`uri = undr.s3-ap-southeast-2.amazonaws.com`](#uri--undrs3-ap-southeast-2amazonawscom)
    -   [`uri = undr.s3-website-ap-southeast-2.amazonaws.com`](#uri--undrs3-website-ap-southeast-2amazonawscom)
    -   [`uri = dvin548rgfj0n.cloudfront.net`](#uri--dvin548rgfj0ncloudfrontnet)
    -   [`uri = d1juofrn4vv0j9.cloudfront.net`](#uri--d1juofrn4vv0j9cloudfrontnet)
    -   [`uri = www.undr.space`](#uri--wwwundrspace)

## Develop

```sh
npm install
npm run watch
# open build/index.html
```

## Deploy

```sh
aws configure
```

```sh
npm run lint
npm run build
aws s3api put-object --bucket undr --key index.html --content-type 'text/html' --body build/index.html
aws cloudfront create-invalidation --distribution-id E1Y0XU2SEIEYXC --paths '/index.html'
```

## URL

### `uri = undr.s3-ap-southeast-2.amazonaws.com`

Amazon S3.

| URL                                                                                                                                                        | Effect                                                                        |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `http://{uri}`, `http://{uri}?(.+)`, `http://{uri}/`, `http://{uri}/?(.+)`, `https://{uri}`, `https://{uri}?(.+)`, `https://{uri}/`, `https://{uri}/?(.+)` | returns an XML file list                                                      |
| `http://{uri}/(.+)`                                                                                                                                        | returns the S3 object at `$1` if `$1` is a valid path and error 404 otherwise |

URL parameters (query string):

-   `list-type`: `2`
-   `delimiter`: `/`
-   `encoding-type`: `url`
-   `max-keys`: `1000000`
-   `prefix`: `dvs09/`

### `uri = undr.s3-website-ap-southeast-2.amazonaws.com`

Amazon S3 static website hosting.

| URL                             | Effect                                                                                                    |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `http://{uri}`                  | times out                                                                                                 |
| `http://{uri}`, `http://{uri}/` | returns index.html                                                                                        |
| `http://{uri}/(.+)`             | returns the S3 object at $1 if $1 is a valid path and redirect to `https://www.undr.space/#/$1` otherwise |

### `uri = dvin548rgfj0n.cloudfront.net`

Cloudfront with origin `undr.s3.ap-southeast-2.amazonaws.com`. Forwards URL parameters.

| URL                                                                        | Effect                                                   |
| -------------------------------------------------------------------------- | -------------------------------------------------------- |
| `http://{uri}`, `http://{uri}/(.*)`, `https://{uri}`, `https://{uri}/(.*)` | returns `http://undr.s3.ap-southeast-2.amazonaws.com/$1` |

### `uri = d1juofrn4vv0j9.cloudfront.net`

Cloudfront with origin `undr.s3-website-ap-southeast-2.amazonaws.com`. Does not forward URL parameters.

| URL                                                                        | Effect                                                           |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `http://{uri}`, `http://{uri}/(.*)`, `https://{uri}`, `https://{uri}/(.*)` | returns `http://undr.s3-website-ap-southeast-2.amazonaws.com/$1` |

### `uri = www.undr.space`

DNS CNAME `d1juofrn4vv0j9.cloudfront.net`
