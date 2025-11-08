import sys
from pathlib import Path

# Parameters from user log
RA_DEG = 6.201691
DEC_DEG = 48.005705
UTC_DT = (2025, 11, 3, 19, 15, 23)  # UTC
MPC_CODE = "N87"
LAT_DEG = 43.4
LON_DEG = 87.1
SEARCH_RADIUS_DEG = 0.01  # 36 arcsec
H_LIMIT = 16.0

BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
MPCORB_PATH = BASE_DIR / "gui/mpc_variables/MPCORB.DAT"
EPHEMERIS_PATH = BASE_DIR / "gui/ephemeris/de421.bsp"

print("[debug] Params:")
print(f"  RA={RA_DEG} deg, Dec={DEC_DEG} deg, UTC={UTC_DT}, MPC={MPC_CODE}, GPS=({LAT_DEG}N,{LON_DEG}E), 半径={SEARCH_RADIUS_DEG} deg")
print(f"  MPCORB: {MPCORB_PATH}\n  Ephemeris: {EPHEMERIS_PATH}")

try:
    from skyfield.api import load, wgs84
    from skyfield.data import mpc
    from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
    import pandas as pd
    from astropy.coordinates import SkyCoord
    import astropy.units as u
except Exception as e:
    print("[error] Import dependency failed:", e)
    sys.exit(1)

# Basic checks
if not MPCORB_PATH.exists():
    print(f"[error] Missing MPCORB file: {MPCORB_PATH}")
    sys.exit(2)
if not EPHEMERIS_PATH.exists():
    print(f"[error] Missing ephemeris file: {EPHEMERIS_PATH}")
    sys.exit(2)

try:
    ts = load.timescale()
    eph = load(str(EPHEMERIS_PATH))
except Exception as e:
    print("[error] Load ephemeris/timescale failed:", e)
    sys.exit(3)

# Observer & time
try:
    earth = eph['earth']
    observer = earth + wgs84.latlon(LAT_DEG, LON_DEG)
    t = ts.utc(*UTC_DT)
    target = SkyCoord(ra=RA_DEG * u.deg, dec=DEC_DEG * u.deg)
except Exception as e:
    print("[error] Setup observer/time failed:", e)
    sys.exit(4)

# Load MPCORB
print("[debug] Loading MPCORB ...")
try:
    with open(MPCORB_PATH, 'rb') as f:
        df = mpc.load_mpcorb_dataframe(f)
except Exception:
    with open(MPCORB_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        df = mpc.load_mpcorb_dataframe(f)

raw_count = None
try:
    raw_count = len(df)
except Exception:
    pass

# Ensure numeric types for required columns
numeric_cols = [
    'magnitude_H','magnitude_G','mean_anomaly_degrees',
    'argument_of_perihelion_degrees','longitude_of_ascending_node_degrees',
    'inclination_degrees','eccentricity','mean_daily_motion_degrees',
    'semimajor_axis_au'
]
for c in numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')

# H filter
col_H = 'magnitude_H' if 'magnitude_H' in df.columns else ('H' if 'H' in df.columns else None)
if col_H is not None:
    try:
        before = len(df)
        df = df[df[col_H] <= H_LIMIT]
        print(f"[debug] H filter: {before} -> {len(df)} (H <= {H_LIMIT})")
    except Exception as e:
        print("[warn] H filter failed:", e)

print(f"[debug] MPCORB rows (raw): {raw_count}, after filter: {len(df)}")

# Helper to compute RA/DEC and separation for a row
from math import isfinite

def compute_row_sep(row):
    try:
        body = eph['sun'] + mpc.mpcorb_orbit(row, ts, GM_SUN)
        ra_obj, dec_obj, _ = observer.at(t).observe(body).radec()
        ra_deg_obj = ra_obj.hours * 15.0
        dec_deg_obj = dec_obj.degrees
        sep_deg = SkyCoord(ra=ra_deg_obj * u.deg, dec=dec_deg_obj * u.deg).separation(target).deg
        return ra_deg_obj, dec_deg_obj, sep_deg
    except Exception as e:
        return None, None, None

# 1) Try direct lookup for Tweedledee / 9387
cands = pd.DataFrame()
try:
    conds = []
    if 'number' in df.columns:
        conds.append(df['number'] == 9387)
    if 'designation' in df.columns:
        conds.append(df['designation'].astype(str).str.contains('9387', na=False))
    if 'name' in df.columns:
        conds.append(df['name'].astype(str).str.contains('Tweedledee', case=False, na=False))
    if conds:
        import numpy as np
        mask = None
        for c in conds:
            mask = c if mask is None else (mask | c)
        cands = df[mask]
except Exception:
    pass

print(f"[debug] Candidates for (9387) Tweedledee: {len(cands)}")
if len(cands) > 0:
    row = cands.iloc[0]
    ra_d, dec_d, sep_d = compute_row_sep(row)
    print(f"[result] 9387 Tweedledee @ RA={ra_d:.8f} deg, Dec={dec_d:.8f} deg, sep={sep_d*3600.0:.3f} arcsec")
else:
    print("[warn] (9387) not found by quick lookup; proceeding with a limited cone search")

# 2) Limited cone search among brightest N
N = 5000
if col_H is not None and col_H in df.columns:
    df_small = df.sort_values(by=col_H, ascending=True).head(N)
else:
    df_small = df.head(N)

min_sep = None
min_info = None
hits = []
err_count = 0
first_err = None

for _, r in df_small.iterrows():
    try:
        ra_d, dec_d, sep_d = compute_row_sep(r)
        if ra_d is None:
            raise RuntimeError("orbit compute failed")
        if (min_sep is None) or (sep_d < min_sep):
            min_sep = sep_d
            name_dbg = str(r.get('designation', ''))
            min_info = f"{name_dbg} @ RA={ra_d:.8f},Dec={dec_d:.8f}, sep={sep_d*3600.0:.3f} arcsec"
        if sep_d <= SEARCH_RADIUS_DEG:
            hits.append((str(r.get('designation', '')), ra_d, dec_d, sep_d))
    except Exception as e:
        err_count += 1
        if first_err is None:
            first_err = str(e)
        continue

print(f"[debug] Limited search N={len(df_small)}; errors={err_count}; min_sep={None if min_sep is None else (min_sep*3600.0):.3f} arcsec")
if first_err:
    print(f"[debug] First error: {first_err}")

if hits:
    print("[result] Hits within radius:")
    for name, ra_d, dec_d, sep_d in hits:
        print(f"  {name:>12s}  RA={ra_d:.8f}  Dec={dec_d:.8f}  sep={sep_d*3600.0:.3f} arcsec")
else:
    print("[result] No hits within radius.")
    if min_info:
        print("[debug] Nearest candidate:", min_info)

