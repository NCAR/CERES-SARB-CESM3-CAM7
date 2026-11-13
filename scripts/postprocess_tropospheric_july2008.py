#!/usr/bin/env python3
"""Verify the July pair, execute its full DAVINCI pipeline, and preserve history."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
SKILL=Path('/glade/u/home/fillmore/.codex/skills/postprocess-ceres-davinci/scripts')


def main():
    plan=json.loads((REPO/'config/tropospheric-july2008.json').read_text())
    data=Path(plan['data_root'])
    config=REPO/'analyses/davinci/tropospheric-july2008-v1.yaml'
    def run(*args):
        subprocess.run([str(x) for x in args],cwd=REPO,check=True)
    run(sys.executable,REPO/'scripts/verify_tropospheric_july2008.py')
    run(sys.executable,SKILL/'preflight_analysis.py',config,'--project-root',REPO,'--data-root',data)
    run(sys.executable,'-m','davinci_monet.cli.app','run',config)
    audit=subprocess.check_output([sys.executable,str(SKILL/'audit_analysis_output.py'),str(data/'runs/tropospheric-july2008-v1')],text=True)
    print(audit,flush=True)
    if not json.loads(audit)['passed']:
        raise ValueError('DAVINCI artifact audit failed')
    (data/'runs/tropospheric-july2008-v1/audit.json').write_text(audit)
    # Archive precisely this experiment's history/log files, with collision and
    # copy checks. Restarts remain in the case's unique scratch directories.
    sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for case in plan['cases'].values():
        archive=data/'model-output/tropospheric-july2008-v1'/case['name']
        archive.mkdir(parents=True,exist_ok=True)
        files=sorted(Path(case['rundir']).glob('*.cam.h0*.nc'))
        files+=sorted(Path(case['rundir']).glob('*.log.*'))
        manifest=[]
        for source in files:
            target=archive/source.name
            expected=sha(source)
            if target.exists() and sha(target)!=expected:
                raise ValueError('History archive collision: '+str(target))
            if not target.exists(): shutil.copy2(source,target)
            if sha(target)!=expected: raise ValueError('History archive checksum mismatch')
            manifest.append({'source':str(source),'archive':str(target),'bytes':target.stat().st_size,'sha256':expected})
        (archive/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    main()
