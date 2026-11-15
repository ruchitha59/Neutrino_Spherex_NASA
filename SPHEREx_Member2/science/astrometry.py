"""Time parsing and optional catalogue-coordinate propagation."""
from __future__ import annotations

from astropy.time import Time
from astropy.coordinates import SkyCoord
import astropy.units as u


def parse_observation_time(timestamp):
    """Preserve the original timestamp and return a normalized UTC ISO string."""
    if timestamp is None or str(timestamp).strip() == "":
        return {"original": timestamp, "utc_isot": None, "scale": None, "error": "Timestamp missing."}
    try:
        time = Time(str(timestamp), format="isot", scale="utc")
        return {
            "original": str(timestamp),
            "utc_isot": time.utc.isot,
            "scale": "utc",
            "mjd_utc": float(time.utc.mjd),
            "jd_utc": float(time.utc.jd),
            "error": None,
        }
    except Exception as exc:
        return {"original": str(timestamp), "utc_isot": None, "scale": None,
                "error": f"{type(exc).__name__}: {exc}"}


def propagate_catalogue_position(ra_deg, dec_deg, reference_epoch,
                                 target_epoch, pm_ra_cosdec_masyr=None,
                                 pm_dec_masyr=None, parallax_mas=None,
                                 radial_velocity_kms=None, catalogue=None):
    """Propagate only when catalogue astrometry and its provenance are supplied."""
    if pm_ra_cosdec_masyr is None or pm_dec_masyr is None:
        return {
            "available": False,
            "reason": "Catalogue proper-motion components were not supplied.",
            "catalogue": catalogue,
        }
    kwargs = {
        "ra": float(ra_deg) * u.deg,
        "dec": float(dec_deg) * u.deg,
        "pm_ra_cosdec": float(pm_ra_cosdec_masyr) * u.mas / u.yr,
        "pm_dec": float(pm_dec_masyr) * u.mas / u.yr,
        "obstime": Time(reference_epoch),
        "frame": "icrs",
    }
    if parallax_mas is not None and float(parallax_mas) > 0:
        kwargs["distance"] = (1000.0 / float(parallax_mas)) * u.pc
    if radial_velocity_kms is not None and "distance" in kwargs:
        kwargs["radial_velocity"] = float(radial_velocity_kms) * u.km / u.s
    coord = SkyCoord(**kwargs)
    propagated = coord.apply_space_motion(new_obstime=Time(target_epoch))
    return {
        "available": True,
        "ra_deg": float(propagated.ra.deg),
        "dec_deg": float(propagated.dec.deg),
        "catalogue": catalogue,
        "reference_epoch": str(reference_epoch),
        "target_epoch": str(target_epoch),
        "method": "Astropy SkyCoord.apply_space_motion",
    }
