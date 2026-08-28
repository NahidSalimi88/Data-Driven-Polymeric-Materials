"""
ASMI plate indentation protocol (CubOS) with legacy Hertz-fit modulus analysis.

This script combines two previous versions of the ASMI workflow:

  * The OLD script talked to the CNC/GRBL stage directly over serial and did all
    of its own contact detection, position tracking, and Hertzian-contact curve
    fitting to compute the sample's elastic modulus (E) from force/indentation
    data.

  * The NEW script drives the same hardware through CubOS's `ProtocolBuilder` /
    `Protocol` layer (homing, motion bounds checking, offline validation,
    campaign bookkeeping, and measurement persistence to a SQLite `DataStore`),
    but only dumped the raw per-well arrays to CSV without computing E.

This version keeps the CubOS hardware/protocol layer for everything that
touches the gantry and the ASMI instrument (homing, moves, the closed-loop
`indentation` measurement, validation, run bookkeeping), and re-attaches the
legacy analysis pipeline (rolling smoothing, fixed-window Hertz fit with
iterative contact-point correction, probe-compliance-corrected elastic
modulus, and per-well plots) on top of the data CubOS records.

NOTES — confirmed against the real `VernierASMI.indentation()` driver:
  1. Unlike the old GRBL script, the new driver has NO built-in contact
     detection. `indentation()` just steps `step_size` mm at a time from
     `measurement_height` all the way down to `indentation_limit_height`
     (or until `force_limit` is exceeded), recording force at every step
     regardless of whether the probe has touched the sample yet. So the
     recorded `z_positions` are *not* pre-zeroed to first contact — the
     sweep includes the "approach" region above the gel too. This script
     re-implements a contact-point estimate (`estimate_contact_index`)
     from the force trace itself, mirroring what the old script's baseline
     + threshold logic used to do, before running the fixed-window Hertz
     fit. Confirm `threshold_sigma`/`sustain` below actually separate noise
     from real contact for your gels — tune if wells get skipped or contact
     is detected too early/late.
  2. `corrected_force_n` in the driver is simply `raw_force_n - baseline_avg`
     (a baseline subtraction, not a shape/geometry correction) — and it
     keeps the same sign convention as the old raw sensor (more negative
     under compression). `FORCE_SOURCE` below defaults to
     "corrected_forces" and the fit flips its sign to match the legacy
     positive-force-under-compression convention. NOTE: the exported
     `asmi_measurements.corrected_forces`/`raw_forces` column names are
     still assumed, not confirmed — verify against `data_store.py`.
  3. `force_limit` in the protocol (`method_kwargs`) is in Newtons (hard
     safety cutoff, `abs(corrected) > force_limit` aborts descent) — not
     the old script's raw-sensor-unit cutoff of `-45`. The `10.0` N
     currently set is a placeholder; for a soft hydrogel this is likely far
     too high and should be tuned down (e.g. sub-1 N) once you know your
     gel's real force range, so a run actually aborts before over-loading
     the probe/sample.
  
"""

import sys
import csv
import json
import time
import sqlite3
import threading
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as pyplot
from scipy.optimize import curve_fit

# --- Append CubOS root paths to load data modules ---
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from protocol_engine.builder import ProtocolBuilder, wells
from data import (
    DataStore,
    DataReader,
    create_campaign_for_protocol_run,
    default_database_path,
)

# --- PATH CONFIGURATIONS ---
CONFIG_DIR = Path(__file__).resolve().parent / "configs"

# --- PROBE / INDENTER PHYSICAL CONSTANTS (steel sphere tip) ---
PROBE_RADIUS_M = 0.00235       # m
PROBE_POISSON_RATIO = 0.28
PROBE_E_PA = 1.8e11            # Pa

# --- HERTZ FIT CONFIGURATION (fixed window, same as legacy script) ---
FIT_DEPTH_MIN = 0.1            # mm
FIT_DEPTH_MAX = 0.5            # mm
D0_TOLERANCE = 0.01            # mm, stop iterating once |d0| is under this
MAX_D0_ITERATIONS = 50
LOW_E_CORRECTION_THRESHOLD = 660_000  # Pa

# Which measurement column to run the Hertz fit on. See NOTES (2) above.
FORCE_SOURCE = "corrected_forces"    # "raw_forces" or "corrected_forces"

# Contact-point detection (replaces the old script's live threshold logic,
# since the new driver's fixed sweep doesn't stop/zero at contact). See
# NOTES (1) above — tune per your noise/gel characteristics if needed.
CONTACT_NOISE_SAMPLES = 10     # points at the start of the sweep used as noise floor
CONTACT_THRESHOLD_SIGMA = 4.0  # stds above noise floor counted as "real" force
CONTACT_SUSTAIN_SAMPLES = 3    # consecutive points required above threshold


# --- ASMI Z HEIGHTS (labware-relative; see NOTES and the deck-height
# discussion — tune per gel batch/well geometry) ---
MEASUREMENT_HEIGHT = -6      # mm, action plane = top of the well
INDENTATION_LIMIT_HEIGHT = -8.7 # mm, deepest allowed descent
INTERWELL_SCAN_HEIGHT = 5.0     # mm above MEASUREMENT_HEIGHT, safe transit height between wells


# --------------------------------------------------------------------------
# Hardware / protocol layer (CubOS)
# --------------------------------------------------------------------------

def build_indentation_protocol(selected_wells, whole_plate=False):
    """
    Build the ASMI indentation protocol via CubOS.

    `add_scan` only takes a whole `plate` (no arbitrary well subset) but
    handles interwell travel (`interwell_scan_height`) for you — so it's
    used whenever `whole_plate` is True. For an arbitrary subset (modes
    1-3: individual/row/column), `add_scan` can't be used, so this falls
    back to a manual `add_measure` loop. `add_move`'s `travel_z` only
    works with literal/named XYZ targets, not deck-target strings like
    "plate.B8" — so between wells we just move to the next well's deck
    target directly (no travel_z) and let CubOS resolve a safe transit
    height for that move itself.
    """
    protocol_builder = ProtocolBuilder.with_setup(
        gantry_path=CONFIG_DIR / "gantry" / "cub_xl_asmi.yaml",
        deck_path=CONFIG_DIR / "deck" / "asmi_deck.yaml",
    )

    protocol_builder.add_position("park_position", [10.0, 10.0, 40.0])
    protocol_builder.add_home()
    protocol_builder.add_command(
        "breakpoint",
        message="Check the plate, samples, probe alignment, and cables. Press Enter to start.",
    )

    method_kwargs = {
        "step_size": 0.02,
        "force_limit": 10.0,   # Newtons — hard abort cutoff; placeholder, see NOTES (3) at top of file
        "baseline_samples": 20,
        "measure_with_return": False,
    }

    if whole_plate:
        # Whole-plate scan: add_scan loops every well itself and retracts
        # to interwell_scan_height between them.
        protocol_builder.add_scan(
            plate="plate",
            instrument="asmi",
            method="indentation",
            measurement_height=MEASUREMENT_HEIGHT,
            interwell_scan_height=INTERWELL_SCAN_HEIGHT,
            indentation_limit_height=INDENTATION_LIMIT_HEIGHT,
            method_kwargs=method_kwargs,
        )
    else:
        # Specific subset: manual per-well loop, with an explicit retract +
        # transit move to each well's XY at INTERWELL_SCAN_HEIGHT before
        # descending, so consecutive wells don't drag the probe sideways
        # through a partially-indented well or a plate wall.
        for i, well in enumerate(selected_wells):
            if i > 0:
                protocol_builder.add_move(
                    instrument="asmi",
                    position=f"plate.{well}",
                )
            protocol_builder.add_measure(
                instrument="asmi",
                position=f"plate.{well}",
                indentation_limit_height=INDENTATION_LIMIT_HEIGHT,
                measurement_height=MEASUREMENT_HEIGHT,
                method="indentation",
                method_kwargs=method_kwargs,
            )

    protocol_builder.add_move(
        instrument="asmi",
        position="park_position",
        travel_z=25.0,
    )

    return protocol_builder.build(source_path=__file__)


def _as_list(value):
    """asmi_measurements array columns may come back as JSON text or,
    depending on the sqlite3.Row conversion, already-decoded Python lists."""
    return json.loads(value) if isinstance(value, str) else value


def fetch_raw_well_data(db_path, campaign_id, unique_wells, quiet=False, retries=3, after_timestamp=None):
    """
    Pull each well's most recent ASMI measurement, keyed by the real
    `well_id` from the experiments join.

    NOTE: this intentionally does NOT filter by `campaign_id`.
    `create_campaign_for_protocol_run()` creates one campaign row and
    returns its id, but `protocol.run(campaign=filename)` appears to
    record experiments/measurements under a different campaign than that
    id (empirically: filtering by our captured `campaign_id` finds zero
    rows for wells that clearly *did* get measured). The old GRBL-era
    script sidestepped this the same way — it never filtered by campaign
    either, just took the most recent N rows overall. This keeps that
    "most recent" fallback, but keyed by `well_id` (safe against
    misordered/missing wells) instead of raw row count (which silently
    mismatches if any well produced zero or multiple rows).

    `campaign_id` is still accepted/kept as an argument in case this gets
    revisited once it's clear how CubOS actually links protocol.run()
    experiments to a campaign row.

    Also pulls `baseline_std`, measured from `baseline_samples` static
    readings taken before any motion — a cleaner noise reference than
    estimating it from the first few points of the (moving) sweep itself.

    `quiet=True` suppresses the "no rows found" print — used when polling
    live during a run, where "not measured yet" is the expected, common
    case rather than something worth logging every second.
    `retries` handles the rare "database is locked" hiccup from reading
    concurrently while CubOS's own connection is writing a new row.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            with DataReader(db_path) as reader:
                query = """
                SELECT m.*, e.well_id
                FROM asmi_measurements m
                JOIN experiments e ON m.experiment_id = e.id
                WHERE e.well_id IN ({placeholders})
                """.format(placeholders=",".join("?" * len(unique_wells)))
                params = list(unique_wells)
                if after_timestamp is not None:
                    query += " AND m.timestamp > ?"
                    params.append(after_timestamp)
                query += " ORDER BY m.id DESC"  
                
                cursor = reader.connection.execute(query, params)
                rows = [dict(r) for r in cursor.fetchall()]
            break
        except sqlite3.OperationalError as exc:
            last_exc = exc
            time.sleep(0.3 * (attempt + 1))
    else:
        raise last_exc

    well_data = {}
    for row in rows:
        well = row["well_id"]
        if well in well_data:
            continue  # already have this well's most recent row (rows are id DESC)
        well_data[well] = (
            _as_list(row["z_positions"]),
            _as_list(row["raw_forces"]),
            _as_list(row["corrected_forces"]),
            row.get("baseline_std"),
        )

    missing = [w for w in unique_wells if w not in well_data]
    if missing and not quiet:
        print(f"No asmi_measurements rows found for: {missing}")

    return well_data


# --------------------------------------------------------------------------
# Legacy Hertz-contact analysis (ported from the GRBL-era script)
# --------------------------------------------------------------------------

# Kept for reference only — the original script already disabled this
# shape-correction table (its `correct_force` returned early). Left here,
# unused, in case you want to re-enable a height/Poisson's-ratio-dependent
# force correction later.
_LEGACY_SHAPE_CORRECTION_TABLE = "see original get_start_stats-era script"


def hertz_model(depth, A, d0):
    return A * np.power(np.clip(depth - d0, 0, None), 1.5)


def find_E(A, p_ratio):
    """
    Convert the Hertz fit coefficient A into the sample's elastic modulus
    (Pa), using Hertz contact theory and subtracting out the compliance of
    the steel probe itself (treated as effectively rigid but not infinitely
    so).
    """
    actual_A = A * pow(1000, 1.5)  # mm -> m unit correction on the fit coefficient
    E_star = (actual_A * 0.75) / pow(PROBE_RADIUS_M, 0.5)
    E_inv = (
        1 / (E_star * (1 - pow(p_ratio, 2)))
        - (1 - pow(PROBE_POISSON_RATIO, 2)) / (PROBE_E_PA * (1 - pow(p_ratio, 2)))
    )
    return 1 / E_inv


def adjust_E(E):
    """Empirical correction for soft samples, calibrated below ~660 kPa."""
    if E < LOW_E_CORRECTION_THRESHOLD:
        factor = 457 * pow(E, -0.457)
        return E / factor
    return E


def estimate_contact_index(force, known_baseline_std=None):
    """
    Estimate the index where the probe first contacts the sample.

    The new driver's `indentation()` has no built-in contact detection — it
    sweeps the full range regardless — so this replaces the old script's
    live "value < baseline - 0.02" threshold check. The noise floor uses
    the real `baseline_std` recorded by the driver (measured from
    `baseline_samples` static readings *before* any motion) when available
    — that's cleaner than re-estimating noise from the first few points of
    the moving sweep. Falls back to estimating from the first
    `CONTACT_NOISE_SAMPLES` sweep points if `known_baseline_std` isn't
    given (e.g. older DB rows without the column, or a direct/offline
    call). Looks for the first run of `CONTACT_SUSTAIN_SAMPLES`
    consecutive points that clear `CONTACT_THRESHOLD_SIGMA` standard
    deviations above the floor — the same "don't trust a single noisy
    sample" idea as the old script's false-alarm reset, just applied to
    already-collected data instead of live.

    Returns (index_or_None, diagnostics_dict) — diagnostics are always
    returned so the caller can explain a None result instead of just
    printing "no data".
    """
    n = CONTACT_NOISE_SAMPLES
    sustain = CONTACT_SUSTAIN_SAMPLES
    diagnostics = {
        "noise_mean": None, "noise_std": None,
        "threshold": None, "max_force": float(np.max(force)) if len(force) else None,
        "min_force": float(np.min(force)) if len(force) else None,
        "noise_source": None,
    }
    if len(force) == 0:
        return None, diagnostics

    if known_baseline_std is not None and known_baseline_std > 0:
        # corrected_force_n already has baseline_avg subtracted, so the
        # noise floor is centered at 0 — only the spread (std) is needed.
        noise_mean = 0.0
        noise_std = float(known_baseline_std)
        diagnostics["noise_source"] = "db_baseline_std"
        start = 0
    else:
        if len(force) <= n:
            return None, diagnostics
        noise_mean = float(np.mean(force[:n]))
        noise_std = float(np.std(force[:n]))
        diagnostics["noise_source"] = "estimated_from_sweep"
        start = n

    threshold = noise_mean + CONTACT_THRESHOLD_SIGMA * max(noise_std, 1e-6)
    diagnostics.update(noise_mean=noise_mean, noise_std=noise_std, threshold=threshold)

    for i in range(start, len(force)):
        window = force[i:i + sustain]
        if len(window) == 0:
            break
        # Near the end of the sweep there may be fewer than `sustain` points
        # left (the descent often stops right around the moment of contact,
        # e.g. reaching indentation_limit_height or force_limit) — accept
        # whatever points remain as long as all of them clear the threshold.
        if np.all(window > threshold):
            return i, diagnostics
    return None, diagnostics

TERMINAL_LOW_FRACTION = 0.15
TERMINAL_SUSTAIN_SAMPLES = 15


def refine_to_terminal_rise(force, contact_idx, sustain=TERMINAL_SUSTAIN_SAMPLES, low_frac=TERMINAL_LOW_FRACTION):
    """
    Some wells show a false initial contact (a bump or small spike, maybe a
    thin surface layer on the gel) before the real Hertzian rise begins.
    Searches backward from the end of the sweep for the last long stretch
    of low force (below low_frac of the final force) — right after that
    stretch is where the real contact starts. If no such stretch exists
    after the current contact_idx (i.e. a clean well like A3), returns
    contact_idx unchanged.
    """
    threshold = low_frac * force[-1]
    n = len(force)
    for i in range(n - sustain, contact_idx - 1, -1):
        window = force[i:i + sustain]
        if len(window) == sustain and np.all(window < threshold):
            return i + sustain
    return contact_idx


    
def prepare_well_arrays(z_positions, forces, baseline_std=None):
    """
    Shared prep used by both the diagnostic plot and the fit: sign-flip and
    smooth the force trace (corrected_force_n -> legacy positive-under-
    compression convention), and run contact detection on it.
    Returns (z, force_smoothed, contact_idx_or_None, contact_diagnostics).
    """
    z = np.asarray(z_positions, dtype=float)
    force = -np.asarray(forces, dtype=float)
    force = pd.Series(force).rolling(window=3, min_periods=1, center=True).mean().to_numpy()
    contact_idx, diagnostics = estimate_contact_index(force, known_baseline_std=baseline_std)
    if contact_idx is not None:
        contact_idx = refine_to_terminal_rise(force, contact_idx)       
    return z, force, contact_idx, diagnostics


def fit_well_modulus(z, force, contact_idx, p_ratio, well_label=""):
    """
    Run the legacy Hertz-fit pipeline (fixed-window fit -> iterative
    contact-point refinement -> probe-corrected E) on one well's already
    contact-detected data. Returns a result dict, or None if the fit fails.
    """
    print(f"Well {well_label}: contact detected at sample {contact_idx} "
          f"(z={z[contact_idx]:.3f} mm)")

    # Descent decreases z, so depth-past-contact = z_at_contact - z.
    depth = z[contact_idx] - z
    run_array = np.column_stack([depth, force])

    def select_fit_window(arr):
        mask = (arr[:, 0] >= FIT_DEPTH_MIN) & (arr[:, 0] <= FIT_DEPTH_MAX)
        return arr[mask, 0], arr[mask, 1]

    d_fit, f_fit = select_fit_window(run_array)
    if len(d_fit) < 3:
        print(f"Well {well_label}: not enough points in the "
              f"{FIT_DEPTH_MIN}-{FIT_DEPTH_MAX} mm fit window, skipping.")
        return None

    try:
        params, covariance = curve_fit(hertz_model, d_fit, f_fit, p0=[2.0, 0.03], maxfev=5000)
        fit_A, fit_d0 = float(params[0]), float(params[1])
    except Exception as exc:
        print(f"Well {well_label}: Hertz fit failed ({exc}), skipping.")
        return None

    count = 0
    while abs(fit_d0) > D0_TOLERANCE and count < MAX_D0_ITERATIONS:
        count += 1
        run_array[:, 0] -= fit_d0
        d_fit, f_fit = select_fit_window(run_array)
        if len(d_fit) < 3:
            break
        try:
            params, covariance = curve_fit(hertz_model, d_fit, f_fit, p0=[2.0, 0.03], maxfev=5000)
            fit_A, fit_d0 = float(params[0]), float(params[1])
        except Exception:
            break

    E = round(adjust_E(find_E(fit_A, p_ratio)).real)
    err = np.sqrt(np.diag(covariance))
    std_dev = round(find_E(err[0], p_ratio))
    d_fit, f_fit = select_fit_window(run_array)

    return {
        "well": well_label,
        "E": E,
        "std_dev": std_dev,
        "depth_fit": d_fit,
        "force_fit": f_fit,
        "fit_A": fit_A,
        "n_points": len(d_fit),
    }


def plot_well_fit(result, filename_stub, output_dir):
    depth_fit, force_fit = result["depth_fit"], result["force_fit"]
    if len(depth_fit) <= 1:
        return
    d_model = np.linspace(min(depth_fit), max(depth_fit), 100)
    f_model = result["fit_A"] * np.power(d_model, 1.5)

    pyplot.figure(figsize=(8, 5))
    pyplot.scatter(depth_fit, force_fit, color="blue", alpha=0.5, label="Data")
    pyplot.plot(d_model, f_model, color="red", label=f"Hertz (E={result['E']} Pa)")
    pyplot.title(f"Well {result['well']}")
    pyplot.xlabel("Indentation (mm)")
    pyplot.ylabel("Force (N)")
    pyplot.legend()
    pyplot.grid(True)
    pyplot.savefig(output_dir / f"Plot_{result['well']}_{filename_stub}.png")
    pyplot.close()


def plot_raw_sweep(z, force, well_label, filename_stub, output_dir, contact_idx=None, diagnostics=None):
    """
    Always-saved diagnostic plot of the raw (smoothed, sign-flipped) force
    trace vs. Z for one well — independent of whether contact was found or
    the Hertz fit succeeded. This is what to check when a well comes back
    "no data": is there actually a force rise in the trace, and if so, why
    didn't estimate_contact_index() catch it?
    """
    pyplot.figure(figsize=(8, 5))
    pyplot.plot(z, force, color="tab:blue", marker=".", markersize=3, label="Force (smoothed)")
    if contact_idx is not None:
        pyplot.axvline(z[contact_idx], color="green", linestyle="--",
                        label=f"Detected contact (z={z[contact_idx]:.3f})")
    if diagnostics and diagnostics.get("threshold") is not None:
        pyplot.axhline(diagnostics["threshold"], color="red", linestyle=":",
                        label=f"Contact threshold ({diagnostics['threshold']:.4f} N)")
    pyplot.gca().invert_xaxis()  # z decreases with depth; show descent left-to-right
    pyplot.title(f"Well {well_label} — raw sweep (diagnostic)")
    pyplot.xlabel("Z position (mm, descending →)")
    pyplot.ylabel("Force, positive under compression (N)")
    pyplot.legend()
    pyplot.grid(True)
    pyplot.savefig(output_dir / f"RawSweep_{well_label}_{filename_stub}.png")
    pyplot.close()


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == "__main__":
    cols = ["A", "B", "C", "D", "E", "F", "G", "H"]
    rows = [str(r) for r in range(1, 13)]

    # --- STEP 1: CAMPAIGN FILENAME ---
    bad_name = True
    while bad_name:
        filename = input("Enter the output filename (no spaces): ").strip()
        if " " in filename:
            print("Invalid name: Filename must not contain spaces.")
        elif filename == "":
            print("Invalid name: Filename cannot be empty.")
        else:
            bad_name = False

    # --- STEP 2: WELL SELECTION ---
    entered = False
    entry_wells = []
    unique_wells = []
    while not entered:
        print("\nSelect Well Mode:")
        print("  1: Individual well entry")
        print("  2: Entire row(s)")
        print("  3: Entire column(s)")
        print("  4: Whole 96-well plate")
        mode = input("Select mode (1/2/3/4): ")

        if mode == "1":
            more = True
            while more:
                well = input("Enter well (e.g. A1) or leave empty to finish: ").strip().upper()
                if well == "":
                    more = False
                elif len(well) < 2 or well[0] not in cols or well[1:] not in rows:
                    print("Error: Out of standard 96-well range.")
                else:
                    entry_wells.append(well)
        elif mode == "2":
            more = True
            while more:
                row = input("Enter row number (1-12) or leave empty to finish: ").strip()
                if row == "":
                    more = False
                elif row not in rows:
                    print("Error: Invalid row number.")
                else:
                    for col in cols:
                        entry_wells.append(col + row)
        elif mode == "3":
            more = True
            while more:
                col = input("Enter column letter (A-H) or leave empty to finish: ").strip().upper()
                if col == "":
                    more = False
                elif col not in cols:
                    print("Error: Invalid column letter.")
                else:
                    for row in rows:
                        entry_wells.append(col + row)
        elif mode == "4":
            full_plate = list(wells("plate", rows="A:H", columns=range(1, 13)))
            entry_wells = [w.split(".")[-1] for w in full_plate]

        unique_wells = []
        for w in entry_wells:
            if w not in unique_wells:
                unique_wells.append(w)

        print(f"\nCurrently selected wells: {unique_wells}")
        correct = input("Confirm selected wells? (Y/N): ")
        if correct.lower() == "y":
            entered = True
            whole_plate = (mode == "4")
        else:
            entry_wells = []

    # --- STEP 3: POISSON'S RATIO ---
    pr_ratios = {}
    same_ratio = input("\nUse the same Poisson's Ratio for all wells? (Y/N): ")
    if same_ratio.lower() == "y":
        pr = float(input("Enter Poisson's Ratio value (0.3-0.5): "))
        pr_ratios = {w: pr for w in unique_wells}
    else:
        for w in unique_wells:
            pr_ratios[w] = float(input(f"Enter Poisson's Ratio for {w} (0.3-0.5): "))

    # --- STEP 4: BUILD & OFFLINE VALIDATION ---
    print("\n🔨 Building Protocol...")
    protocol = build_indentation_protocol(unique_wells, whole_plate=whole_plate)

    print("🔍 Running Offline Safety Preflight Validation...")
    try:
        protocol.validate()
        print("✓ Offline Validation Succeeded! No safety violations detected.")
    except Exception as e:
        print(f"❌ Protocol Validation Failed: {e}")
        sys.exit(1)

    # --- STEP 5+6: RUN ON HARDWARE, LIVE PER-WELL RESULTS AS EACH FINISHES ---
    print(f"\n🚀 Preparing hardware run for campaign: '{filename}'...")

    db_path = default_database_path()
    output_dir = Path(r"C:\Users\nahid.salimi\CubOS\data\results") / filename
    output_dir.mkdir(parents=True, exist_ok=True)
    results_filename = output_dir / f"{filename}_results.csv"
    with open(results_filename, "w", newline="") as res_file:
        csv.writer(res_file).writerow(["well", "E_Pa", "std_dev_Pa"])

    analysis_results = []

    def process_well(well, well_entry):
        """Analyze, plot, and print results for one well as soon as its data
        is available — same logic as before, just pulled out so it can run
        per-well instead of only after the whole plate finishes."""
        z_positions, raw_forces, corrected_forces, baseline_std = well_entry
        forces = raw_forces if FORCE_SOURCE == "raw_forces" else corrected_forces

        well_df = pd.DataFrame({
            "Z_Position": z_positions,
            "Raw_Force": raw_forces,
            "Corrected_Force": corrected_forces,
        })
        well_df.to_csv(output_dir / f"{well}_asmi_raw_data.csv", index=False)

        if len(z_positions) == 0:
            print(f"Well {well}: no data points, skipping.")
            analysis_results.append([well, "no data", "no data"])
            return

        z, force, contact_idx, diag = prepare_well_arrays(
            z_positions, forces, baseline_std=baseline_std
        )

        # Always save a diagnostic plot, whether or not contact/fit succeeded.
        plot_raw_sweep(z, force, well, filename, output_dir,
                        contact_idx=contact_idx, diagnostics=diag)

        if contact_idx is None:
            def _fmt(v):
                return f"{v:.4f}" if v is not None else "n/a"
            print(
                f"Well {well}: no contact detected "
                f"(source={diag['noise_source']}, "
                f"noise_mean={_fmt(diag['noise_mean'])} N, "
                f"noise_std={_fmt(diag['noise_std'])} N, "
                f"threshold={_fmt(diag['threshold'])} N, "
                f"max force seen={_fmt(diag['max_force'])} N). "
                f"Check RawSweep_{well}_{filename}.png — if the trace clearly "
                f"rises but never sustains {CONTACT_SUSTAIN_SAMPLES} points above "
                f"threshold, lower CONTACT_THRESHOLD_SIGMA or CONTACT_SUSTAIN_SAMPLES."
            )
            analysis_results.append([well, "no data", "no data"])
            return

        fit = fit_well_modulus(z, force, contact_idx, pr_ratios[well], well_label=well)
        if fit is None:
            analysis_results.append([well, "no data", "no data"])
            return

        print(f"✅ Well {well} done — E = {fit['E']} Pa, Error = {fit['std_dev']} Pa "
              f"({fit['n_points']} points in fit window)")
        plot_well_fit(fit, filename, output_dir)

        analysis_results.append([well, fit["E"], fit["std_dev"]])
        
        with open(results_filename, "a", newline="") as res_file:
            csv.writer(res_file).writerow([well, fit["E"], fit["std_dev"]])

    # Run the (blocking) hardware protocol in a background thread so the
    # main thread is free to poll the database and report each well the
    # moment its data lands, instead of waiting for all 96 to finish.
    run_state = {"exit_code": 0, "hardware_results": [], "campaign_id": None, "done": False}

    def run_protocol_thread():
        
        data_store = DataStore(db_path)   
        gantry_path = CONFIG_DIR / "gantry" / "cub_xl_asmi.yaml"
        deck_path = CONFIG_DIR / "deck" / "asmi_deck.yaml"
        protocol_path = Path(__file__).resolve()
        try:
            run_state["campaign_id"] = create_campaign_for_protocol_run(
                data_store,
                gantry_path=str(gantry_path),
                deck_path=str(deck_path),
                gantry_file=str(gantry_path),
                deck_file=str(deck_path),
                protocol_file=str(protocol_path),
                description=filename,
            )
            run_state["hardware_results"] = protocol.run(campaign=filename)
        except Exception as exc:
            print(f"\nERROR during execution: {exc}")
            traceback.print_exc()
            run_state["exit_code"] = 1
        finally:
            run_state["done"] = True
            data_store.close()

    worker = threading.Thread(target=run_protocol_thread, daemon=True)
    worker.start()

    with sqlite3.connect(str(db_path)) as _tmp_conn:
        run_start_time = _tmp_conn.execute("SELECT datetime('now')").fetchone()[0]

    print("📡 Watching for completed wells (live results as each finishes)...\n")
    pending = list(unique_wells)
    try:
        while not run_state["done"] and pending:
            time.sleep(2.0)
            well_data = fetch_raw_well_data(db_path, run_state["campaign_id"], pending, quiet=True, after_timestamp=run_start_time)
            for well in list(pending):
                if well in well_data:
                    process_well(well, well_data[well])
                    pending.remove(well)
    except KeyboardInterrupt:
        print("\nAborted by user (Ctrl+C). Waiting for hardware to settle...")
        run_state["exit_code"] = 130

    worker.join()

    # Final catch-up pass, in case any wells finished between the last poll
    # and the thread ending (or if polling was skipped due to Ctrl+C).
    if pending:
        well_data = fetch_raw_well_data(db_path, run_state["campaign_id"], pending, quiet=True, after_timestamp=run_start_time)
        for well in list(pending):
            if well in well_data:
                process_well(well, well_data[well])
                pending.remove(well)
    for well in pending:
        print(f"Well {well}: no data recorded, skipping.")
        analysis_results.append([well, "no data", "no data"])

    # --- Final Excel summary, in addition to the CSV written incrementally above ---
    try:
        results_df = pd.DataFrame(analysis_results, columns=["well", "E_Pa", "std_dev_Pa"])
        excel_path = output_dir / f"{filename}_results.xlsx"
        results_df.to_excel(excel_path, index=False)
        print(f"\n📊 Excel summary saved to: {excel_path}")
    except Exception as exc:
        print(f"\n⚠️ Could not write Excel summary: {exc}")

    exit_code = run_state["exit_code"]
    hardware_results = run_state["hardware_results"]

    print("\n" + "=" * 60)
    if exit_code == 0:
        print(f"Protocol complete — {len(hardware_results)} steps executed successfully.")
    else:
        print(f"Protocol did not complete fully — {len(hardware_results)} steps executed before exit.")
    print("=" * 60)
    print("\nSummary of final results:")
    for res in analysis_results:
        print(f"Well {res[0]}: E = {res[1]} Pa, Uncertainty = {res[2]} Pa")

    if exit_code:
        sys.exit(exit_code)