#!/usr/bin/env python3
"""Submit the configured matched pair through CIME, recording jobs and source hashes."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import yaml

REPO=Path(__file__).resolve().parents[1]


def main():
    plan=json.loads((REPO/'config/tropospheric-july2008.json').read_text())
    spec=importlib.util.spec_from_file_location('setup',REPO/'scripts/setup_tropospheric_july2008.py')
    setup=importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
    env=setup.clean_environment(plan)
    root=Path(plan['data_root'])/'logs/tropospheric-july2008-v1'
    root.mkdir(parents=True,exist_ok=True)
    sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    exe=Path(plan['exeroot'])/'cesm.exe'
    if not exe.is_file(): raise ValueError('Build the paired executable first')
    a,b=(Path(plan['cases'][m]['path']) for m in ('tropo','column'))
    normalize=lambda p: re.sub(r'aod_tropo_only\s*=\s*\.(?:true|false)\.', 'aod_tropo_only = FLAG', '\n'.join(line for line in p.read_text().splitlines() if line.strip() and not line.lstrip().startswith('!')), flags=re.I)
    if normalize(a/'user_nl_cam')!=normalize(b/'user_nl_cam'):
        raise ValueError('Paired namelists differ beyond aod_tropo_only')
    if (a/'SourceMods').resolve()!=(b/'SourceMods').resolve():
        raise ValueError('Expected the paired cases to share the same SourceMods and executable')
    for mode,case in plan['cases'].items():
        if (root/('submission-'+mode+'.json')).exists():
            raise ValueError('Submission already recorded for '+mode)
    jobs=[]
    for mode,case in plan['cases'].items():
        path=Path(case['path'])
        completed=subprocess.run(['./case.submit'],cwd=path,env=env,text=True,capture_output=True)
        log=root/('submit-'+mode+'.log')
        log.write_text(completed.stdout+'\n'+completed.stderr)
        completed.check_returncode()
        ids=set(re.findall(r'\b\d+\.desched\d+\b',completed.stdout+'\n'+completed.stderr))
        if len(ids)!=1: raise ValueError('Expected one model PBS job ID; inspect '+str(log))
        job=ids.pop(); jobs.append(job)
        submitted=datetime.now(timezone.utc).isoformat()
        proof={'job_id':job,'case':case,'submitted_utc':submitted,'executable_sha256':sha(exe),
               'submission_log':str(log),'case_provenance':str(path/'tropospheric-experiment.json')}
        (root/('submission-'+mode+'.json')).write_text(json.dumps(proof,indent=2)+'\n')
        run_id=case['name']+'--20261111'
        record={
            'schema_version':1,'run_id':run_id,'case_name':case['name'],'run_kind':'cesm','execution_date':'2026-11-11',
            'purpose':'Matched whole-column versus tropospheric-only MODIS scaling, ten June spinup days and July 2008 profiles',
            'simulation':{'calendar':'NO_LEAP','start_date':'2008-06-21','end_date':'2008-08-01','spinup_days':10,'duration_days':41,'analysis_records':248,'history_cadence_hours':3},
            'configuration':{'model':plan['model'].upper(),'compset':'FHIST' if plan['model']=='cam6' else 'HIST_CAM70%LT_CLM60%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV_SESP',
                             'resolution':'f09_f09_mg17','aerosol':'MAM4','aod_tropo_only':case['aod_tropo_only'],
                             'case_plan':'config/tropospheric-july2008.json','case_provenance':proof['case_provenance'],
                             'executable_sha256':proof['executable_sha256']},
            'scheduler':{'system':'Derecho PBS','job_id':job,'scheduler_state':'Q','tasks':128,'threads':1,'walltime_requested':plan['walltime'],'memory_requested':plan['memory']},
            'status':{'stage':'queued','model_outcome':'not-run','summary':'Matched July model job submitted through CIME; build and case preflight passed.'},
            'outputs':{'primary':case['rundir'],'case_dir':case['path'],'run_dir':case['rundir']},
            'validation':{category:{'status':'pending','summary':'Awaiting full July integration and paired verification.'} for category in ('structural','numeric','davinci','science')},
            'provenance':{'recorded_at':submitted,'sources':['config/tropospheric-july2008.json',str(log),proof['case_provenance']]}}
        # Resolve the actual expanded compset from this case, not a remembered alias.
        record['configuration']['compset']=subprocess.check_output(['./xmlquery','COMPSET','--value'],cwd=path,env=env,text=True).strip()
        (REPO/'run_history/records'/(run_id+'.yaml')).write_text(yaml.safe_dump(record,sort_keys=False,width=110))
        print(mode,job,flush=True)
    out=Path(plan['data_root'])/'runs/tropospheric-july2008-v1'
    out.mkdir(parents=True,exist_ok=True)
    command=['qsub','-W','depend=afterok:'+':'.join(jobs),'-o',str(out/'davinci-pbs.log'),str(REPO/'scripts/postprocess_tropospheric_july2008.pbs')]
    result=subprocess.check_output(command,text=True).strip()
    (root/'postprocess-submission.json').write_text(json.dumps({'job_id':result,'depends_on':jobs,'command':command},indent=2)+'\n')
    print('Verification and DAVINCI:',result,flush=True)


if __name__=='__main__':
    main()
