from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage import measure, morphology

import g49c_spot_raw_geometry_ri002 as core
from g49c_spot_raw_geometry_ri002_v2 import radiographic_surface_line

MAX_PHYSICAL_DEPTH_UM = 300.0
SURFACE_ATTACHMENT_TOLERANCE_PX = 5.0


def segment_surface_attached(stretched: np.ndarray, line: dict, threshold_mult: float, surface_shift_px: int) -> np.ndarray:
    """Target-native cavity segmentation with a physical surface-attachment gate.

    Candidate contrast regions are restricted to the material layer beneath the pre-laser
    air/Ti64 interface. A valid vapor-depression/keyhole component must intersect a small
    band immediately below that interface. This prevents disconnected bulk-metal texture
    and detector artifacts from being relabeled as a cavity.

    This gate uses only current X-ray geometry and pre-laser surface reference. It does not
    inspect future absorptance, RI002 predictive outcomes, or Scan holdout data.
    """
    threshold = threshold_mult * float(np.mean(stretched))
    binary = stretched > threshold
    h, w = binary.shape
    xx = np.arange(w, dtype=float)
    sy = core.surface_y(line, xx) + float(surface_shift_px)
    yy = np.arange(h, dtype=float)[:, None]

    slope = float(line['slope_y_per_x'])
    norm = math.sqrt(1.0 + slope * slope)
    normal_depth_px = (yy - slope * xx[None, :] - float(line['intercept_y_px']) - float(surface_shift_px)) / norm
    max_depth_px = MAX_PHYSICAL_DEPTH_UM / core.PIXEL_UM

    # Physical support: inside Ti64, no deeper than nominal material thickness.
    binary &= normal_depth_px >= 0.0
    binary &= normal_depth_px <= max_depth_px

    binary = morphology.binary_dilation(binary, morphology.diamond(1))
    binary = ndi.binary_fill_holes(binary)
    binary = morphology.binary_erosion(binary, morphology.disk(1))
    binary = morphology.remove_small_objects(binary.astype(bool), min_size=core.MIN_OBJECT_AREA_PX)

    lab = measure.label(binary, connectivity=2)
    props = measure.regionprops(lab)
    attached = []
    for p in props:
        if p.area < core.MIN_OBJECT_AREA_PX:
            continue
        coords = p.coords
        py = coords[:, 0].astype(float)
        px = coords[:, 1].astype(float)
        d = (py - slope * px - float(line['intercept_y_px']) - float(surface_shift_px)) / norm
        if np.nanmin(d) <= SURFACE_ATTACHMENT_TOLERANCE_PX:
            attached.append((p, float(np.nanmin(d)), float(np.nanmax(d))))

    if not attached:
        return np.zeros_like(binary, dtype=bool)

    # Prefer the surface-nearest component; break ties by larger physical support.
    chosen = min(attached, key=lambda item: (item[1], -item[0].area))[0]
    return lab == chosen.label


def main() -> None:
    core.robust_surface_line = radiographic_surface_line
    core.segment_reference = segment_surface_attached
    core.main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

    out = Path(sys.argv[4])
    with (out / 'G49C_ADJUDICATION.txt').open('a', encoding='utf-8') as f:
        f.write('SEGMENTATION_V2=REJECTED_PRELASER_FALSE_OBJECT_43_OF_43\n')
        f.write('SEGMENTATION_V3=SURFACE_ATTACHED_PHYSICAL_SUPPORT_GATE\n')
        f.write(f'SURFACE_ATTACHMENT_TOLERANCE_PX={SURFACE_ATTACHMENT_TOLERANCE_PX}\n')
        f.write(f'MAX_PHYSICAL_DEPTH_UM={MAX_PHYSICAL_DEPTH_UM}\n')
        f.write('SEGMENTATION_V3_USES_FUTURE_ABSORPTANCE=FALSE\n')
        f.write('SEGMENTATION_V3_USES_SCAN=FALSE\n')


if __name__ == '__main__':
    main()
