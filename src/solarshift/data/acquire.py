"""Download a complete archive or validate an existing one, then extract known files."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
from urllib.request import Request, urlopen
import zipfile

from .common import read_config, sha256, write_json


def extract_archive(archive: Path, destination: Path, expected: list[str]) -> list[dict]:
    # Validate the entire archive before writing any member. Never salvage partial ZIPs silently.
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Archive contains duplicate member names.")
        missing = set(expected) - set(names)
        if missing:
            raise ValueError(f"Archive missing required files: {sorted(missing)}")
        bad = source.testzip()
        if bad:
            raise ValueError(f"Archive checksum failure: {bad}")
        destination.mkdir(parents=True, exist_ok=True)
        members = expected + [name for name in names if name.endswith('.pdf') or name == 'README.md']
        records = []
        for name in members:
            if Path(name).name != name:
                raise ValueError(f"Unexpected nested archive path: {name}")
            target = destination / name
            with source.open(name) as original, target.open('wb') as output:
                shutil.copyfileobj(original, output)
            records.append({'filename': name, 'bytes': target.stat().st_size, 'sha256': sha256(target)})
        return records


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.zip.part')
    request = Request(url, headers={'User-Agent': 'SolarShiftAI/0.1 research-data-acquisition'})
    with urlopen(request, timeout=90) as response, temporary.open('wb') as output:
        shutil.copyfileobj(response, output)
        expected = response.headers.get('Content-Length')
    if expected and temporary.stat().st_size != int(expected):
        raise ValueError('Incomplete download: byte count differs from Content-Length. Retry acquisition.')
    with zipfile.ZipFile(temporary) as source:
        if source.testzip():
            raise ValueError('Downloaded archive failed CRC validation.')
    temporary.replace(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/data.toml')
    parser.add_argument('--archive', type=Path, help='Use a previously downloaded complete ZIP')
    args = parser.parse_args()
    data = read_config(args.config)['data']
    archive = args.archive or data['raw_dir'] / 'Ausgrid_solar_home_data.zip'
    if not args.archive:
        download(data['source_url'], archive)
    files = extract_archive(archive, data['raw_dir'], data['files'])
    record = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_url': data['source_url'], 'acquisition': 'local_archive' if args.archive else 'download',
              'archive_sha256': sha256(archive), 'archive_bytes': archive.stat().st_size,
              'archive_crc_check': 'passed', 'files': files,
              'provenance_limit': 'CRC/SHA verify consistency, not independent Ausgrid authenticity.',
              'licence_status': 'Mirror states CC BY 3.0 Australia; original grant not independently recovered.'}
    write_json(data['raw_dir'] / 'acquisition.json', record)
    print(f"Validated complete archive and extracted {len(files)} files to {data['raw_dir']}")


if __name__ == '__main__':
    main()
