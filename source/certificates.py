import atexit
import pathlib
import shutil
import sys
import tempfile
import typing


temporary_directory: typing.Optional[pathlib.Path] = None


def _cleanup() -> None:
    global temporary_directory
    if temporary_directory is not None:
        shutil.rmtree(temporary_directory)
        temporary_directory = None


atexit.register(_cleanup)


def bundle() -> str:
    global temporary_directory
    if temporary_directory is not None:
        return str(temporary_directory / "ca-bundle.crt")
    if sys.platform == "win32":
        return None
    if sys.platform == "darwin":
        # from https://github.com/sheagcraig/MacSesh/blob/master/macsesh/keychain.py
        from Security import (
            errSecSuccess,
            kSecClass,
            kSecReturnRef,
            kSecMatchLimit,
            kSecMatchLimitAll,
            SecItemCopyMatching,
            kSecClassCertificate,
            kSecMatchTrustedOnly,
            SecItemExport,
            kSecFormatUnknown,
            SecTrustCopyAnchorCertificates,
        )
        from urllib3.contrib._securetransport.bindings import CoreFoundation, Security

        certificates = []
        result_code, result = SecItemCopyMatching(
            {
                kSecClass: kSecClassCertificate,
                kSecReturnRef: True,
                kSecMatchLimit: kSecMatchLimitAll,
                kSecMatchTrustedOnly: True,
            },
            None,
        )
        if result_code == errSecSuccess:
            certificates.extend(result)
        result_code, result = SecTrustCopyAnchorCertificates(None)
        if result_code == errSecSuccess:
            certificates.extend(result)
        if len(certificates) == 0:
            return None
        return_code, pem_data = SecItemExport(certificates, kSecFormatUnknown, 0, None, None)
        if return_code != errSecSuccess:
            return None
        temporary_directory = pathlib.Path(tempfile.mkdtemp())
        with open(temporary_directory / "ca-bundle.crt", "wb") as certificates_bundle:
            certificates_bundle.write(pem_data)
        return str(temporary_directory / "ca-bundle.crt")

    # from https://golang.org/src/crypto/x509/root_linux.go
    for path in (
        "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu/Gentoo etc.
        "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora/RHEL 6
        "/etc/ssl/ca-bundle.pem",  # OpenSUSE
        "/etc/pki/tls/cacert.pem",  # OpenELEC
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # CentOS/RHEL 7
        "/etc/ssl/cert.pem",  # Alpine Linux
    ):
        if pathlib.Path(path).is_file():
            return str(path)
    certificates_paths = []
    for path in (
        "/etc/ssl/certs",  # SLES10/SLES11
        "/etc/pki/tls/certs",  # Fedora/RHEL
        "/system/etc/security/cacerts",  # Android
    ):
        if path.is_dir():
            for subpath in path.iterdir():
                if subpath.is_file():
                    certificates_paths.append(subpath)
            if len(certificates_path) > 0:
                temporary_directory = pathlib.Path(tempfile.mkdtemp())
                with open(temporary_directory / "ca-bundle.crt", "wb") as certificates_bundle:
                    for path in certificates_path:
                        with open(path, "rb") as certificate:
                            certificates_bundle.write(certificate.read())
                return str(temporary_directory / "ca-bundle.crt")
    return None
