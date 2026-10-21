import zipfile

import pytest

from solarshift.data.acquire import extract_archive


def test_only_expected_data_extracted_and_manifest_hashed(tmp_path):
    archive = tmp_path / 'data.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('year.csv', 'fixture')
        z.writestr('unused.txt', 'not requested')
    files = extract_archive(archive, tmp_path / 'raw', ['year.csv'])
    assert files[0]['sha256'] == 'f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d'
    assert not (tmp_path / 'raw' / 'unused.txt').exists()


def test_incomplete_archive_cannot_be_salvaged_silently(tmp_path):
    archive = tmp_path / 'partial.zip'
    archive.write_bytes(b'PK\x03\x04incomplete')
    with pytest.raises(zipfile.BadZipFile):
        extract_archive(archive, tmp_path / 'raw', ['year.csv'])
    assert not (tmp_path / 'raw').exists()


def test_missing_expected_member_fails_before_extraction(tmp_path):
    archive = tmp_path / 'data.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('wrong.csv', 'fixture')
    with pytest.raises(ValueError, match='missing required'):
        extract_archive(archive, tmp_path / 'raw', ['year.csv'])
