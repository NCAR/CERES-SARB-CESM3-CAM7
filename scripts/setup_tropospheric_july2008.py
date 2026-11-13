#!/usr/bin/env python3
"""Configure a matched July pair without modifying a completed case or model checkout."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]
FIELDS = ['AODVIS', 'AODVISdn', 'FSNTC', 'AODNDG_OBS', 'AODNDG_MODEL_PRE', 'AODNDG_MODEL_POST',
          'AODNDG_RATIO', 'AODNDG_MASK', 'AODNDG_TROP_PRE', 'AODNDG_TROP_POST',
          'AODNDG_FIXED_PRE', 'AODNDG_FIXED_POST', 'AODNDG_TROP_P', 'AODNDG_TROP_LEV',
          'AODNDG_TROP_MASK', 'AODNDG_PMID', 'AODNDG_MMR_PRE', 'AODNDG_MMR_POST',
          'AODNDG_NUM_PRE', 'AODNDG_NUM_POST']


def clean_environment(plan):
    env = os.environ.copy()
    for key in ('CONDA_PREFIX', 'CONDA_DEFAULT_ENV', 'CONDA_SHLVL', 'CONDA_EXE', 'CONDA_PYTHON_EXE', 'PYTHONPATH'):
        env.pop(key, None)
    shim = REPO / 'build/python311'
    shim.mkdir(parents=True, exist_ok=True)
    for name in ('python', 'python3'):
        target = shim / name
        if not target.exists():
            target.symlink_to(plan['python'])
    env['PATH'] = str(shim) + ':' + ':'.join(p for p in env['PATH'].split(':') if not any(
        word in p.lower() for word in ('miniforge', 'miniconda', 'anaconda', '/conda/')))
    env['OMP_NUM_THREADS'] = env['OPENBLAS_NUM_THREADS'] = '1'
    return env


def replace_namelist(text, settings):
    # Each assignment extends to the next assignment, including multiline lists.
    matches = list(re.finditer(r'(?m)^[ \t]*([A-Za-z_]\w*)[ \t]*=', text))
    pieces = [text[:matches[0].start()]] if matches else [text]
    for i, match in enumerate(matches):
        key = match.group(1).lower()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        if key not in settings and not re.fullmatch(r'f(?:incl|excl)\d+', key):
            pieces.append(text[match.start():end])
    pieces.append('\n! Matched whole-column/tropospheric July experiment.\n')
    pieces.extend(key + ' = ' + value + '\n' for key, value in settings.items())
    return ''.join(pieces)


def pin_launcher(case, plan):
    launcher = case / '.case.run'
    text = launcher.read_text()
    text = '#!' + plan['python'] + '\n' + text.split('\n', 1)[1]
    cleanup = """import os, sys
os.environ['PATH'] = {shim!r} + ':' + ':'.join(
    p for p in os.environ['PATH'].split(':')
    if not any(w in p.lower() for w in ('miniforge', 'miniconda', 'anaconda', '/conda/')))
for key in ('CONDA_PREFIX','CONDA_DEFAULT_ENV','CONDA_SHLVL','CONDA_EXE','CONDA_PYTHON_EXE','PYTHONPATH'):
    os.environ.pop(key, None)
""".format(shim=str(REPO / 'build/python311'))
    text = text.replace('import os, sys\n', cleanup, 1)
    # CIME versions differ in whether machine defaults already specify memory.
    def memory(match):
        line = re.sub(r':mem=[^:\s]+', '', match.group(0))
        return line + ':mem=' + plan['memory']
    text, count = re.subn(r'(?m)^#PBS[^\n]*-l select=[^\n]+', memory, text)
    if count != 1:
        raise ValueError('Expected one PBS select directive')
    launcher.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('tropo', 'column'), required=True)
    args = parser.parse_args()
    plan = json.loads((REPO / 'config/tropospheric-july2008.json').read_text())
    for root, expected in ((Path(plan['cesm_root']), plan['cesm_commit']),
                           (Path(plan['cesm_root']) / 'components/cam', plan['cam_commit'])):
        actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise ValueError('Pinned model revision changed: ' + str(root))
    selected = plan['cases'][args.mode]
    case = Path(selected['path'])
    for path in (case, Path(selected['rundir'])):
        if path.exists():
            raise SystemExit('Refusing existing case/run directory: ' + str(path))
    if args.mode == 'tropo' and Path(plan['exeroot']).exists():
        raise SystemExit('Refusing existing build directory: ' + plan['exeroot'])
    env = clean_environment(plan)
    primary = Path(plan['cases']['tropo']['path'])
    base = Path(plan['base_case']) if args.mode == 'tropo' else primary
    if args.mode == 'tropo':
        if hashlib.sha256((base / 'user_nl_cam').read_bytes()).hexdigest() != plan['base_user_nl_sha256']:
            raise ValueError('The pinned source case namelist changed')
        for name, expected in plan['base_source_files_sha256'].items():
            if hashlib.sha256((base / 'SourceMods/src.cam' / name).read_bytes()).hexdigest() != expected:
                raise ValueError('The pinned source case overlay changed: ' + name)
    else:
        if not (Path(plan['exeroot']) / 'cesm.exe').is_file():
            raise ValueError('Build the tropospheric case before cloning its executable')
        proof = json.loads((primary / 'tropospheric-experiment.json').read_text())
        for name, expected in proof['source_files_sha256'].items():
            if hashlib.sha256((primary / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Paired SourceMods changed since configuration: ' + name)
    command = [str(Path(plan['cesm_root']) / 'cime/scripts/create_clone'), '--case', str(case),
               '--clone', str(base), '--cime-output-root', plan['output_root'], '--project', plan['project']]
    if args.mode == 'column':
        command.append('--keepexe')
    subprocess.run(command, env=env, check=True)

    def run(*args):
        subprocess.run(list(args), cwd=case, env=env, check=True)

    if args.mode == 'tropo':
        mods = case / 'SourceMods/src.cam'
        if plan['model'] == 'cam6':
            spec = importlib.util.spec_from_file_location('prepare', REPO / 'scripts/prepare_cam6_usermods.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            package = Path(plan['data_root']) / 'usermods/tropospheric-july2008-v1'
            module.prepare(Path(plan['cesm_root']), package, Path(plan['observation_root']), check=package.exists())
            for source in (package / 'SourceMods/src.cam').iterdir():
                shutil.copy2(source, mods / source.name)
        else:
            # Native checkout already carries the pinned SP2 hooks/silent optics.
            # Preserve the base case's calendar-fixed observation reader.
            for name in ('aod_nudging_kernel.F90', 'aod_nudging_optics.F90', 'aod_nudging_intr.F90'):
                shutil.copy2(REPO / 'src/cam' / name, mods / name)
            for name in ('namelist_definition.xml', 'namelist_defaults_cam.xml'):
                shutil.copy2(REPO / 'src/cam/namelist' / name, mods / name)
    settings = {
        'aod_nudge_on': '.true.', 'aod_tropo_only': '.true.' if args.mode == 'tropo' else '.false.',
        'aod_obs_path': "'" + plan['observation_root'] + "/'",
        'aod_obs_template': "'" + plan['observation_template'] + "'",
        'aod_beg_ymd': '20000401', 'aod_end_ymd': '20220331', 'aod_diag_on': '.true.',
        'empty_htapes': '.true.', 'avgflag_pertape': "'I'", 'nhtfrq': '-3', 'mfilt': '8', 'iradsw': '-1',
        'fincl1': ', '.join("'" + name + "'" for name in FIELDS)}
    namelist = case / 'user_nl_cam'
    namelist.write_text(replace_namelist(namelist.read_text(), settings))
    values = {'RUN_TYPE': 'startup', 'RUN_STARTDATE': plan['start_date'], 'STOP_OPTION': 'ndays', 'STOP_N': 41,
              'REST_OPTION': 'ndays', 'REST_N': 10, 'DOUT_S': 'FALSE', 'RESUBMIT': 0, 'CONTINUE_RUN': 'FALSE',
              'RUNDIR': selected['rundir']}
    if args.mode == 'tropo':
        values.update(EXEROOT=plan['exeroot'], GMAKE_J=plan['build_jobs'], NTASKS=128, NTHRDS=1, ROOTPE=0)
    for key, value in values.items():
        run('./xmlchange', str(key) + '=' + str(value))
    # Modern CIME clones can copy a CAM cache containing the original case's
    # usr_src path. Regenerate this private cache so namelists see this overlay.
    cache = case / 'Buildconf/camconf/config_cache.xml'
    if cache.exists():
        cache.unlink()
    run('./case.setup')
    run('./xmlchange', 'JOB_QUEUE=' + plan['queue'], '--subgroup', 'case.run')
    run('./xmlchange', 'JOB_WALLCLOCK_TIME=' + plan['walltime'], '--subgroup', 'case.run')
    pin_launcher(case, plan)
    run('./preview_namelists')
    run('./check_input_data')
    run('./xmlquery', 'COMPSET,GRID,CAM_CONFIG_OPTS,RUN_STARTDATE,STOP_N,EXEROOT,RUNDIR,NTASKS_ATM,NTHRDS_ATM')
    run('./preview_run')
    provenance = {'plan': plan, 'mode': args.mode, 'source_files_sha256': {
        str(p.relative_to(case)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((case / 'SourceMods/src.cam').iterdir()) if p.is_file()},
        'user_nl_sha256': hashlib.sha256(namelist.read_bytes()).hexdigest()}
    (case / 'tropospheric-experiment.json').write_text(json.dumps(provenance, indent=2)+'\n')
    print('Configured:', case, flush=True)


if __name__ == '__main__':
    main()
