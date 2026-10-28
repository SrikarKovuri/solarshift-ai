"""Prepare genuine marker replay data from an official archive; no retraining."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import zipfile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from solarshift.substation.ausgrid import read_csv_bytes, canonical_name


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def cleaned_readings(w,scales):
    w=w.sort_values(['substation','date']).reset_index(drop=True)
    if w.duplicated(['substation','date']).any() or not w.unit.str.upper().eq('MW').all():
        raise ValueError('Invalid source keys or units')
    x=w[list(range(96))].to_numpy(float);flags=np.where(np.isfinite(x),0,1).astype('uint8')
    sc=scales.set_index('substation').reindex(w.substation)
    if sc.change_scale.isna().any():raise ValueError('Missing frozen cleaning scale')
    d=np.diff(x,axis=1);z=abs(d-sc.change_median.to_numpy()[:,None])/sc.change_scale.to_numpy()[:,None]
    flags[:,1:-1]|=((z[:,:-1]>15)&(z[:,1:]>15)&(np.sign(d[:,:-1])!=np.sign(d[:,1:]))).astype('uint8')*2
    run=np.zeros(len(w),dtype=int)
    for j in range(1,96):
        run=np.where(np.isfinite(x[:,j])&(x[:,j]==x[:,j-1]),run+1,0)
        flags[run>=15,j-15:j+1]|=4
    flags[w.date.isin(pd.to_datetime(['2023-10-01','2024-04-07'])).to_numpy()]|=8
    x[flags>0]=np.nan
    half=x.reshape(-1,48,2).mean(2).astype('float32')
    return pd.DataFrame(dict(site=np.repeat(w.substation.to_numpy(),48),date=np.repeat(w.date.to_numpy(),48),
        hh=np.tile(np.arange(48),len(w)),signed_actual_mw=half.ravel()))


def prepare(output,archive=None):
    assets=ROOT/'demo/assets';manifest=json.loads((assets/'manifest.json').read_text())
    for name,h in manifest['hashes'].items():
        if sha256(assets/name)!=h:raise ValueError(f'Bundled asset checksum mismatch: {name}')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if archive is None:
        archive=output/manifest['archive_name']
        if not archive.exists():
            print('Downloading official Ausgrid FY2024 archive (about 17 MB).',flush=True)
            request=urllib.request.Request(manifest['source_url'],headers={'User-Agent':'SolarShiftAI-research-demo/1.0'})
            partial=archive.with_suffix('.part')
            try:
                with urllib.request.urlopen(request,timeout=90) as response,partial.open('wb') as target:
                    shutil.copyfileobj(response,target)
                if sha256(partial)!=manifest['archive_sha256']:raise ValueError('Official archive changed; see docs/marker_guide.md')
                partial.replace(archive)
            finally:
                partial.unlink(missing_ok=True)
    archive=Path(archive)
    if sha256(archive)!=manifest['archive_sha256']:raise ValueError('Archive checksum differs from the verified research source')
    frames=[]
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not name.lower().endswith('.csv'):continue
            # Inspect the header/first row before parsing the complete site table.
            raw=z.read(name)
            import csv,io
            reader=csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace')))
            next(reader,None);first=next(reader,None)
            if not first or canonical_name(first[1]) not in manifest['sites']:continue
            w=read_csv_bytes(raw);w['substation']=w.substation.map(canonical_name);w['date']=pd.to_datetime(w.date)
            frames.append(w)
    if not frames:raise ValueError('Selected sites missing from the archive')
    readings=cleaned_readings(pd.concat(frames,ignore_index=True),pd.read_csv(assets/'substation_day4/training_cleaning_scales.csv'))
    f=pd.read_parquet(assets/'forecasts.parquet')
    f=f.merge(readings,on=['site','date','hh'],validate='one_to_one')
    f['actual_magnitude_mw']=f.signed_actual_mw.abs()
    for lag,col in [(1,'yesterday_mw'),(7,'weekly_mw')]:
        prev=readings.copy();prev['date']+=pd.Timedelta(days=lag);prev[col]=prev.signed_actual_mw.abs()
        f=f.merge(prev[['site','date','hh',col]],on=['site','date','hh'],validate='one_to_one')
    cols=['actual_magnitude_mw','signed_actual_mw','weekly_mw','yesterday_mw']
    if len(f)!=manifest['intervals'] or not np.isfinite(f[cols]).all().all():raise ValueError('Incomplete demo reconstruction')
    for directory in assets.iterdir():
        if directory.is_dir():shutil.copytree(directory,output/directory.name,dirs_exist_ok=True)
    f.to_parquet(output/'substation_day4/validation_forecasts.parquet',index=False)
    (output/'demo_manifest.json').write_text(json.dumps(dict(**manifest,prepared=True),indent=2)+'\n')
    print(f"Ready: {manifest['site_days']} genuine historical site-days across {len(manifest['sites'])} sites.",flush=True)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,help='Optional manually downloaded original FY2024 ZIP')
    parser.add_argument('--output',type=Path,default=ROOT/'results/generated/marker_demo')
    args=parser.parse_args()
    try:prepare(args.output,args.archive)
    except Exception as exc:
        raise SystemExit(f'Demo setup failed: {exc}\nSee docs/marker_guide.md for the manual-download fallback.')
