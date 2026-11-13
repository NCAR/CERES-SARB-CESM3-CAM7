#!/usr/bin/env python3
"""Verify the complete July pair and prepare numeric inputs for DAVINCI (no rendering)."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from netCDF4 import Dataset, num2date
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASE_FIELDS = ('AODNDG_OBS', 'AODNDG_MODEL_PRE', 'AODNDG_MODEL_POST', 'AODNDG_RATIO', 'AODNDG_MASK',
               'AODNDG_TROP_PRE', 'AODNDG_TROP_POST', 'AODNDG_FIXED_PRE', 'AODNDG_FIXED_POST')
PROFILE_FIELDS = ('AODNDG_MMR_PRE', 'AODNDG_MMR_POST', 'AODNDG_NUM_PRE', 'AODNDG_NUM_POST')


def check_profiles(pre, post, ratio, trop_mask, tropo_only):
    expected = np.where(trop_mask, ratio[:, None, :, :], 1.) if tropo_only else ratio[:, None, :, :]
    if not np.allclose(post, pre*expected, rtol=5.e-6, atol=1.e-22):
        raise ValueError('Aerosol profile does not follow the applied layer scaling')
    protected = ~trop_mask
    delta = post-pre
    maximum = float(np.max(np.abs(delta[protected]))) if protected.any() else 0.
    if tropo_only and maximum != 0.:
        raise ValueError('Nonzero stratospheric/tropopause aerosol increment')
    return maximum


def reduce_run(run_dir, tropo_only):
    all_times, july_times, used = [], [], []
    sums = profile_sums = profile_weights = lat = lon = gw = None
    counts = {'active_cells': 0, 'cell_records': 0, 'low_clamps': 0, 'high_clamps': 0,
              'unclamped_cells': 0, 'protected_profile_cells': 0, 'changed_protected_mass_cells': 0}
    errors = {'ratio': 0., 'total_AOD_update': 0., 'fixed_AOD_change': 0.,
              'protected_MMR_change': 0., 'protected_number_change': 0., 'unclamped_observation': 0.}
    for path in sorted(run_dir.glob('*.cam.h0*.nc')):
        with Dataset(path) as ds:
            ds.set_auto_mask(False)
            dates = num2date(ds['time'][:], ds['time'].units, ds['time'].calendar)
            all_times.extend(str(d) for d in dates)
            take = [i for i, d in enumerate(dates) if (d.year, d.month) == (2008, 7)]
            if not take:
                continue
            july_times.extend(str(dates[i]) for i in take)
            if sums is None:
                lat, lon, gw = (np.asarray(ds[n][:], dtype=float) for n in ('lat', 'lon', 'gw'))
                nlev = len(ds.dimensions['lev'])
                sums = np.zeros((len(lat), len(lon)))
                profile_sums = np.zeros((6, 2*nlev-1))
                profile_weights = np.zeros(2*nlev-1)
            elif not np.array_equal(ds['lat'][:], lat) or not np.array_equal(ds['lon'][:], lon):
                raise ValueError('History grid changed')
            fields = {name: np.asarray(ds[name][take], dtype=float) for name in BASE_FIELDS}
            if not all(np.isfinite(a).all() for a in fields.values()):
                raise ValueError('Nonfinite column diagnostics')
            obs, pre, post, ratio, mask, tpre, tpost, fpre, fpost = (fields[name] for name in BASE_FIELDS)
            trop = np.asarray(ds['AODNDG_TROP_MASK'][take], dtype=bool)
            level = np.asarray(ds['AODNDG_TROP_LEV'][take], dtype=int)
            expected_mask = np.arange(1, nlev+1)[None, :, None, None] > level[:, None, :, :]
            if not ((level >= 1) & (level <= nlev)).all() or not np.array_equal(trop, expected_mask):
                raise ValueError('Native tropopause level and eligible layer mask disagree')
            denominator = tpre if tropo_only else pre
            eligible = (obs >= 0) & (denominator >= .01)
            boundary = np.abs(denominator-.01) < 1.e-8
            if not np.isin(mask, [0, 1]).all() or np.any((mask.astype(bool) != eligible) & ~boundary):
                raise ValueError('Effective nudge mask disagrees with the guards')
            active = mask.astype(bool)
            target = np.maximum(obs-np.maximum(fpre, 0), 0) if tropo_only else obs
            expected_ratio = np.ones_like(ratio)
            expected_ratio[active] = np.clip(target[active]/denominator[active], .1, 10.)
            if not np.allclose(ratio, expected_ratio, rtol=4.e-6, atol=1.e-6):
                raise ValueError('Applied ratio does not fit the eligible residual target')
            predicted = fpre + tpre*ratio if tropo_only else pre*ratio
            if not np.allclose(post, predicted, rtol=4.e-5, atol=2.e-6):
                raise ValueError('Total AOD does not obey fixed plus scaled optical depth')
            if not np.allclose(pre, fpre+tpre, rtol=4.e-6, atol=1.e-6):
                raise ValueError('Pre-update AOD partition is inconsistent')
            if not np.allclose(post, fpost+tpost, rtol=4.e-6, atol=1.e-6):
                raise ValueError('Post-update AOD partition is inconsistent')
            if tropo_only and not np.allclose(fpre, fpost, rtol=4.e-5, atol=2.e-6):
                raise ValueError('Excluded optical depth changed')
            if np.any(np.abs(post[~active]-pre[~active]) > 2.e-7):
                raise ValueError('Inactive columns changed AOD')
            unclamped = active & (expected_ratio > .10001) & (expected_ratio < 9.99999)
            if not np.allclose(post[unclamped], obs[unclamped], rtol=4.e-5, atol=2.e-6):
                raise ValueError('Unclamped total analyzed AOD misses MODIS')
            mmr0, mmr1, num0, num1 = [np.asarray(ds[name][take], dtype=float) for name in PROFILE_FIELDS]
            if not all(np.isfinite(a).all() for a in (mmr0, mmr1, num0, num1)):
                raise ValueError('Nonfinite aerosol profiles')
            mass_error = check_profiles(mmr0, mmr1, ratio, trop, tropo_only)
            number_error = check_profiles(num0, num1, ratio, trop, tropo_only)
            protected = ~trop
            counts['protected_profile_cells'] += int(protected.sum())
            counts['changed_protected_mass_cells'] += int(np.count_nonzero((mmr1 != mmr0) & protected))
            counts['active_cells'] += int(active.sum())
            counts['cell_records'] += active.size
            counts['low_clamps'] += int((active & (ratio <= .10001)).sum())
            counts['high_clamps'] += int((active & (ratio >= 9.99999)).sum())
            counts['unclamped_cells'] += int(unclamped.sum())
            maxima = {'ratio': np.abs(ratio-expected_ratio), 'total_AOD_update': np.abs(post-predicted),
                      'fixed_AOD_change': np.abs(fpost-fpre), 'protected_MMR_change': [mass_error],
                      'protected_number_change': [number_error], 'unclamped_observation': np.abs(post[unclamped]-obs[unclamped])}
            for name, values in maxima.items():
                errors[name] = max(errors[name], float(np.max(values)) if np.size(values) else 0.)
            sums += post.sum(axis=0)
            # Align each column with the *same native index* used by the update.
            # Zero is the excluded tropopause level, positive is above, negative below.
            offset = level[:, None, :, :] - np.arange(1, nlev+1)[None, :, None, None]
            bins = (offset+nlev-1).ravel()
            weights = np.broadcast_to(gw[None, None, :, None], mmr0.shape)
            profile_weights += np.bincount(bins, weights=weights.ravel(), minlength=2*nlev-1)
            for i, values in enumerate((mmr0, mmr1, mmr1-mmr0, num0, num1, num1-num0)):
                profile_sums[i] += np.bincount(bins, weights=(values*weights).ravel(), minlength=2*nlev-1)
            used.append(str(path))
    expected_july = [str(datetime(2008, 7, 1)+timedelta(hours=3*i)) for i in range(248)]
    if july_times != expected_july:
        raise ValueError('Expected exactly the 248 consecutive July samples, with no August boundary')
    allowed_all = [str(datetime(2008, 6, 21)+timedelta(hours=3*i)) for i in range(329)]
    if all_times not in (allowed_all, allowed_all[1:]):
        raise ValueError('Incomplete spinup/July history or missing final August model boundary')
    if not counts['active_cells']:
        raise ValueError('No active MODIS constraints')
    if not tropo_only and not counts['changed_protected_mass_cells']:
        raise ValueError('Whole-column reference does not demonstrate the original stratospheric increments')
    mean = sums/248
    with np.errstate(invalid='ignore', divide='ignore'):
        profiles = profile_sums/profile_weights
    weights2d = np.broadcast_to(gw[:, None], mean.shape)
    summary = {'passed': True, 'troposphere_only': tropo_only, 'run_dir': str(run_dir),
               'history_records': len(all_times), 'first_time': all_times[0], 'last_time': all_times[-1],
               'july_records': len(july_times), 'july_first': july_times[0], 'july_last': july_times[-1],
               'counts': counts, 'maximum_errors': errors, 'global_mean_analyzed_AOD': float(np.sum(mean*weights2d)/weights2d.sum()),
               'profile_alignment': 'Native model-level offset from diagnosed tropopause; zero is excluded, positive above, negative below.',
               'sampling': 'Three-hour instantaneous pre/post updates throughout July; direct increments are distinct from trajectory differences.',
               'history_files': used}
    return summary, mean, profiles, profile_weights, (lat, lon, gw)


def write_inputs(output, column, tropo):
    cs, cm, cp, cw, grid = column
    ts, tm, tp, tw, grid_t = tropo
    if any(not np.array_equal(a, b) for a, b in zip(grid, grid_t)):
        raise ValueError('Paired grids differ')
    lat, lon, gw = grid
    output.mkdir(parents=True, exist_ok=True)
    fields = {'column_aod': (cm, 'Whole-Column Analyzed AOD'),
              'tropospheric_aod': (tm, 'Tropospheric-Scaling Analyzed AOD'),
              'tropospheric_minus_column_aod': (tm-cm, 'Tropospheric Minus Whole-Column AOD')}
    for name, profile in [('maps', False), ('profiles', True)]:
        with Dataset(output/(name+'.nc'), 'w') as ds:
            ds.createDimension('time', 1)
            v = ds.createVariable('time', 'f8', ('time',))
            v[:] = [15.5]
            v.units, v.calendar = 'days since 2008-07-01', 'noleap'
            v.bounds = 'time_bounds'
            ds.createDimension('bnds', 2)
            ds.createVariable('time_bounds', 'f8', ('time', 'bnds'))[:] = [[0., 31.]]
            if profile:
                ds.createDimension('altitude', cp.shape[1])
                v = ds.createVariable('altitude', 'f8', ('altitude',))
                v[:] = np.arange(cp.shape[1])-(cp.shape[1]-1)//2
                v.units = 'Model Levels Relative to Tropopause'
                v.long_name = 'Native model-level offset; zero excluded, positive above, negative below'
                dims = ('time', 'altitude')
                with np.errstate(divide='ignore', invalid='ignore'):
                    fields = {'column_mass': (np.log10(np.where(cp[1] > 0, cp[1], np.nan)), 'Whole-Column Log10 Aerosol MMR (kg/kg)'),
                              'tropospheric_mass': (np.log10(np.where(tp[1] > 0, tp[1], np.nan)), 'Tropospheric Log10 Aerosol MMR (kg/kg)'),
                              'mass_difference': ((tp[1]-cp[1])*1.e9, 'Tropospheric Minus Whole-Column Aerosol MMR'),
                              'column_mass_increment': (cp[2]*1.e9, 'Whole-Column Aerosol Mass Increment'),
                              'tropospheric_mass_increment': (tp[2]*1.e9, 'Tropospheric Aerosol Mass Increment'),
                              'column_number_increment': (cp[5], 'Whole-Column Aerosol Number Increment'),
                              'tropospheric_number_increment': (tp[5], 'Tropospheric Aerosol Number Increment')}
            else:
                for n, values, units in (('lat', lat, 'degrees_north'), ('lon', lon, 'degrees_east'), ('gw', gw, '1')):
                    if n != 'gw': ds.createDimension(n, len(values))
                    v = ds.createVariable(n, 'f8', ('lat' if n == 'gw' else n,))
                    v[:] = values
                    v.units = units
                dims = ('time', 'lat', 'lon')
            for n, (values, label) in fields.items():
                v = ds.createVariable(n, 'f8', dims, fill_value=np.nan, zlib=True)
                v[0] = values
                v.long_name = label
                v.units = '1' if not profile else ('kg-1' if 'number' in n else '1' if n.endswith('_mass') else 'ng/kg')
                v.cell_methods = 'time: mean'
            ds.comparison = 'Matched initialization/forcing, whole-column versus tropospheric-only aerosol scaling'
            ds.profile_weighting = 'Area-weighted mean over July column samples sharing each native tropopause-relative level'
    w = np.broadcast_to(gw[:, None], cm.shape)
    d = tm-cm
    comparison = {'column_global_mean_AOD': cs['global_mean_analyzed_AOD'],
                  'tropospheric_global_mean_AOD': ts['global_mean_analyzed_AOD'],
                  'AOD_bias_tropospheric_minus_column': float(np.sum(w*d)/w.sum()),
                  'AOD_spatial_RMSE': float(np.sqrt(np.sum(w*d*d)/w.sum())),
                  'protected_layer_mass_increment_column': cs['maximum_errors']['protected_MMR_change'],
                  'protected_layer_mass_increment_tropospheric': ts['maximum_errors']['protected_MMR_change'],
                  'protected_layer_number_increment_column': cs['maximum_errors']['protected_number_change'],
                  'protected_layer_number_increment_tropospheric': ts['maximum_errors']['protected_number_change'],
                  'interpretation': 'Zero direct protected-layer increment does not require identical stratospheric profiles between trajectories: transport, physics, and a moving tropopause can create later differences.'}
    return comparison


def main():
    plan = json.loads((REPO/'config/tropospheric-july2008.json').read_text())
    results = {}
    for mode in ('column', 'tropo'):
        results[mode] = reduce_run(Path(plan['cases'][mode]['rundir']), mode == 'tropo')
    output = Path(plan['data_root'])/'analysis-inputs/tropospheric-july2008-v1'
    comparison = write_inputs(output, results['column'], results['tropo'])
    report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'passed': True, 'model': plan['model'],
              'case_plan': plan, 'runs': {m: r[0] for m, r in results.items()}, 'comparison': comparison}
    (output/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(comparison, indent=2))


if __name__ == '__main__':
    main()
