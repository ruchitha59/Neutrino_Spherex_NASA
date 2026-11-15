
"""Conservative SPHEREx valid-pixel masks driven by FITS flag metadata."""
from __future__ import annotations

import re
import numpy as np


# Defined in the SPHEREx Explanatory Supplement v1.3 Table 10.
DOCUMENTED_BAD_FLAGS = {
    "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC", "DICHROIC",
    "MISSING_DATA", "HOT", "COLD", "PHANMISS", "NONLINEAR",
    "PERSIST", "OUTLIER",
}

INFORMATIONAL_FLAGS = {"SOURCE", "FULLSAMPLE"}


def flag_definitions_from_header(header):
    """Read both MSKN/MSKM/MSKD and MP_* flag definitions.

    MSKM values are already bit masks.
    MP_* values are bit positions and are converted to bit masks.
    """
    definitions = {}

    # Original format: MSKN#### / MSKM#### / MSKD####
    for key, value in header.items():
        match = re.fullmatch(r"MSKN(\d{4})", str(key))
        if not match:
            continue

        suffix = match.group(1)
        name = str(value).strip().upper()
        mask = header.get(f"MSKM{suffix}")
        description = header.get(f"MSKD{suffix}")

        if mask is not None:
            definitions[name] = {
                "mask": int(mask),
                "description": (
                    str(description).strip()
                    if description is not None else None
                ),
                "source": "FITS FLAGS header",
            }

    # New format: MP_FLAGNAME = bit position
    for key, value in header.items():
        match = re.fullmatch(r"MP_(.+)", str(key))
        if not match:
            continue

        name = match.group(1).strip().upper()

        try:
            bit_position = int(value)
        except (TypeError, ValueError):
            continue

        if bit_position < 0:
            continue

        definitions[name] = {
            "mask": 1 << bit_position,
            "bit_position": bit_position,
            "description": None,
            "source": "FITS FLAGS header (bit position)",
        }

    return definitions


def build_valid_mask(
    science,
    flags=None,
    variance=None,
    footprint=None,
    flag_definitions=None,
    exclude_flags=None,
):
    """Return (valid_mask, exclusion_counts).

    SOURCE and FULLSAMPLE are informational and are not rejected
    by default.
    """
    data = np.asarray(science)
    valid = np.isfinite(data)

    counts = {
        "non_finite_science": int((~np.isfinite(data)).sum())
    }

    if variance is not None:
        var = np.asarray(variance)

        if var.shape != data.shape:
            raise ValueError(
                "Variance and science arrays must have identical shapes."
            )

        bad = (~np.isfinite(var)) | (var < 0)
        counts["invalid_variance"] = int(bad.sum())
        valid &= ~bad

    if footprint is not None:
        fp = np.asarray(footprint)

        if fp.shape != data.shape:
            raise ValueError(
                "Footprint and science arrays must have identical shapes."
            )

        bad = (~np.isfinite(fp)) | (fp <= 0)
        counts["uncovered"] = int(bad.sum())
        valid &= ~bad

    if flags is not None:
        flag_array = np.asarray(flags)

        if flag_array.shape != data.shape:
            raise ValueError(
                "FLAGS and science arrays must have identical shapes."
            )

        definitions = flag_definitions or {}

        names_to_exclude = (
            set(exclude_flags)
            if exclude_flags is not None
            else set(DOCUMENTED_BAD_FLAGS)
        )

        # Exclude explicitly identified image artifacts.
        for name, info in definitions.items():
            if name in INFORMATIONAL_FLAGS:
                continue

            description = (info.get("description") or "").lower()

            if any(
                word in name.lower()
                for word in (
                    "ghost", "streak", "bloom",
                    "snowball", "halo", "crosstalk",
                )
            ):
                names_to_exclude.add(name)

            if any(
                word in description
                for word in (
                    "ghost", "streak", "bloom",
                    "snowball", "halo", "crosstalk",
                )
            ):
                names_to_exclude.add(name)

        for name in names_to_exclude:
            info = definitions.get(name)

            if not info:
                continue

            bitmask = int(info["mask"])
            bad = (
                flag_array.astype(np.int64) & bitmask
            ) != 0

            counts[f"flag_{name}"] = int(bad.sum())
            valid &= ~bad

    counts["valid_pixels"] = int(valid.sum())
    counts["excluded_pixels"] = int(valid.size - valid.sum())

    return valid, counts
