"""Marker entry point: prepare genuine replay data, then launch Streamlit."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from scripts.prepare_demo import prepare

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,help='Use an existing official FY2024 ZIP instead of downloading')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--full',action='store_true',help='Use existing full local research artifacts')
    args=parser.parse_args()
    output=ROOT/'results/generated' if args.full else ROOT/'results/generated/marker_demo'
    if not args.full:
        try:prepare(output,args.archive)
        except Exception as exc:raise SystemExit(f'{exc}\nSee docs/marker_guide.md for setup help.')
    if args.prepare_only:return
    env=os.environ.copy();env['SOLARSHIFT_RESULTS']=str(output)
    env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    subprocess.run([sys.executable,'-m','streamlit','run',str(ROOT/'streamlit_app.py'),
        '--server.address=127.0.0.1','--browser.gatherUsageStats=false'],cwd=ROOT,env=env,check=True)

if __name__=='__main__':main()
