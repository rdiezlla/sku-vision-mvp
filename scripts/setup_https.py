from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from _launcher_common import CERTS_DIR, command_exists, local_ip_candidates, run_checked


def cert_names() -> list[str]:
    names = ["localhost", "127.0.0.1", "::1"]

    for ip in local_ip_candidates():
        if ip not in names:
            names.append(ip)

    return names


def generate_with_mkcert(certs_dir: Path, names: list[str]) -> None:
    cert_file = certs_dir / "dev-cert.pem"
    key_file = certs_dir / "dev-key.pem"

    run_checked(["mkcert", "-install"], cwd=certs_dir)
    run_checked(
        [
            "mkcert",
            "-cert-file",
            str(cert_file),
            "-key-file",
            str(key_file),
            *names,
        ],
        cwd=certs_dir,
    )

    caroot = subprocess.check_output(["mkcert", "-CAROOT"], text=True).strip()
    root_ca = Path(caroot) / "rootCA.pem"
    if root_ca.exists():
        (certs_dir / "rootCA.pem").write_bytes(root_ca.read_bytes())


def generate_with_openssl(certs_dir: Path, names: list[str], force: bool) -> None:
    root_ca = certs_dir / "rootCA.pem"
    root_key = certs_dir / "rootCA-key.pem"
    cert_file = certs_dir / "dev-cert.pem"
    key_file = certs_dir / "dev-key.pem"

    if force:
        for path in [root_ca, root_key, cert_file, key_file]:
            if path.exists():
                path.unlink()

    if not root_key.exists() or not root_ca.exists():
        run_checked(["openssl", "genrsa", "-out", str(root_key), "4096"], cwd=certs_dir)
        run_checked(
            [
                "openssl",
                "req",
                "-x509",
                "-new",
                "-nodes",
                "-key",
                str(root_key),
                "-sha256",
                "-days",
                "3650",
                "-out",
                str(root_ca),
                "-subj",
                "/CN=SKU Vision Local Dev CA",
            ],
            cwd=certs_dir,
        )

    run_checked(["openssl", "genrsa", "-out", str(key_file), "2048"], cwd=certs_dir)

    with TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        csr = tmp / "dev.csr"
        ext_file = tmp / "openssl-dev.cnf"

        dns_names = [name for name in names if not name.replace(".", "").isdigit() and ":" not in name]
        ip_names = [name for name in names if name not in dns_names]

        lines = [
            "[req]",
            "distinguished_name=req_distinguished_name",
            "req_extensions=v3_req",
            "prompt=no",
            "[req_distinguished_name]",
            "CN=localhost",
            "[v3_req]",
            "subjectAltName=@alt_names",
            "[alt_names]",
        ]

        dns_idx = 1
        for name in dns_names:
            lines.append(f"DNS.{dns_idx}={name}")
            dns_idx += 1

        ip_idx = 1
        for ip in ip_names:
            lines.append(f"IP.{ip_idx}={ip}")
            ip_idx += 1

        ext_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        run_checked(
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(key_file),
                "-out",
                str(csr),
                "-config",
                str(ext_file),
            ],
            cwd=certs_dir,
        )

        run_checked(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(csr),
                "-CA",
                str(root_ca),
                "-CAkey",
                str(root_key),
                "-CAcreateserial",
                "-out",
                str(cert_file),
                "-days",
                "825",
                "-sha256",
                "-extensions",
                "v3_req",
                "-extfile",
                str(ext_file),
            ],
            cwd=certs_dir,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local HTTPS certificates")
    parser.add_argument("--force", action="store_true", help="Regenerate cert and key")
    args = parser.parse_args()

    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    cert_file = CERTS_DIR / "dev-cert.pem"
    key_file = CERTS_DIR / "dev-key.pem"

    if cert_file.exists() and key_file.exists() and not args.force:
        print("Certificados ya existen. Usa --force para regenerar.")
        print(f"- Cert: {cert_file}")
        print(f"- Key : {key_file}")
        print(f"- CA  : {CERTS_DIR / 'rootCA.pem'}")
        return 0

    names = cert_names()
    print(f"Nombres SAN para cert: {', '.join(names)}")

    if command_exists("mkcert"):
        print("Usando mkcert...")
        generate_with_mkcert(CERTS_DIR, names)
    elif command_exists("openssl"):
        print("mkcert no disponible. Usando fallback openssl...")
        generate_with_openssl(CERTS_DIR, names, force=args.force)
    else:
        raise SystemExit(
            "No se encontró mkcert ni openssl. Instala uno de ellos para habilitar HTTPS local."
        )

    print("Certificados generados:")
    print(f"- Cert: {cert_file}")
    print(f"- Key : {key_file}")
    print(f"- CA  : {CERTS_DIR / 'rootCA.pem'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
