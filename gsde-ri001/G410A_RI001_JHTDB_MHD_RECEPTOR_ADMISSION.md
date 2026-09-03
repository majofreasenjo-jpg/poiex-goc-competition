# GMATIVE GSDE G4.10A — RI001 JHTDB Forced MHD Receptor Admission Contract

Date: 2026-09-03

## Status

`G4_10A_RI001_RECEPTOR_ADMISSION=FROZEN_CANDIDATE_PRIMARY`

`PRIMARY_RECEPTOR=JHTDB_FORCED_MHD_1024`

`SENSOR_ONLY_PROXY=FORBIDDEN`

`TARGET_NATIVE_BILINEAR_OPERATOR_REQUIRED=TRUE`

`SCAN_HOLDOUT_REMAINS_SEALED=TRUE`

## Why this receptor

The Johns Hopkins Turbulence Database forced-MHD simulation exposes full 3D time-resolved velocity, pressure, magnetic field and magnetic vector potential fields over 1024 stored frames on a 1024^3 DNS grid. JHTDB also exposes velocity-gradient and magnetic-field-gradient queries. This permits genuine bilinear terms to be reconstructed directly from target-native state fields instead of inferred from scalar sensors.

## RI001 target-native candidate operators

For incompressible MHD, define only quantities reconstructible from current-time fields and spatial gradients:

- fluid self-advection: `Q_uu = (u · grad) u`
- magnetic induction advection: `Q_uB = (u · grad) B`
- magnetic stretching: `Q_Bu = (B · grad) u`
- magnetic self-advection / Lorentz-structure proxy only if the exact target-native governing normalization is frozen before evaluation.

The primary RI001 bilinear contrast is:

`Q_induction = (B · grad)u - (u · grad)B`

because both factors are independently observed target-native vector fields and the interaction is genuinely bilinear.

## Admission gates

A receptor may enter G4.10B only if all gates pass:

1. **STATE_FIELDS** — full spatial vector fields required; scalar/sensor summaries are inadmissible.
2. **BILINEARITY** — candidate term must contain products of independently varying target-native fields or a field with its spatial gradient; polynomial regression surrogates do not count.
3. **NO_TARGET_LEAKAGE** — no future state, future derivative, endpoint or target-derived selection may enter the predictor.
4. **DERIVATIVE_CUSTODY** — gradients must be either obtained directly from JHTDB's derivative service or recomputed from a frozen spatial stencil on raw field cutouts. Method must be declared before scoring.
5. **TEMPORAL_CUSTODY** — development and evaluation times must be frozen; random row CV forbidden.
6. **SPATIAL_CUSTODY** — subvolumes and strides must be frozen before outcome inspection; no post-hoc hotspot selection.
7. **EQUAL_ACCESS_RIVALS** — conventional rivals receive the same u, B and gradients and may construct generic bilinear/polynomial interactions.
8. **NO_NOVELTY_BY_REPARAMETERIZATION** — any RI001 score that is algebraically recoverable from an equal-access conventional representation receives zero distinct information credit.
9. **SOURCE/TARGET FIREWALL** — MHD evidence cannot be transferred back to Navier–Stokes proof status.
10. **ABSTENTION** — failure of any gate means `RI001_RECEPTOR_ADMISSION=HOLD_OR_REJECT`, never proxy substitution.

## Primary evaluation question

Does a source-faithful RI001 quadratic/bilinear decomposition provide a representation, detection or forecasting advantage that survives equal-information rivals on held-out time/spatial blocks?

This is not a test of whether MHD is nonlinear; that is known. It is a test of whether the RI001 structural decomposition contributes algorithmic value beyond conventional same-information constructions.

## Development hierarchy

- **G4.10A**: receptor admission and mathematical contract only.
- **G4.10B**: custody probe, exact API/data availability, frozen small cutout, derivative consistency, no scoring.
- **G4.10C**: development-only operator reconstruction and algebraic redundancy tournament.
- **G4.10D**: only if C survives, blocked temporal/spatial predictive tournament.

## Claim ceiling

`RI001_MHD_ADMISSION != RI001_EMPIRICAL_VALIDATION`

`MHD_BILINEAR_OPERATOR_EXISTS != GSDE_INCREMENTAL_VALUE`

`TARGET_NATIVE_RECONSTRUCTION != NOVELTY_PROVED`

`MHD_RESULT != NAVIER_STOKES_PROOF_EVIDENCE`

No empirical credit is granted at G4.10A. Scan P17 remains unopened.
