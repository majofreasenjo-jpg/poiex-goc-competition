# GMATIVE GSDE G4.10C — RI001 Algebraic Information Negative Seal

Date: 2026-09-03

## Status

`G4_10C_RI001_ALGEBRAIC_INFORMATION_SCREEN=CLOSED_EXACT_NEGATIVE_SEAL`

`RI001_RAW_INFORMATION_NOVELTY=DENIED_UNDER_EQUAL_ACCESS_BILINEAR_BASIS`

`RI001_STRUCTURAL_ALGORITHMIC_CREDIT=OPEN_UNTESTED`

`RI001_SOURCE_MATH_FALSIFIED=FALSE`

`PREDICTIVE_SCORING_PERFORMED=FALSE`

## Setup

Let, at one target-native spacetime point,

- `u in R^d` be velocity,
- `B in R^d` be magnetic field,
- `G_u = grad(u) in R^(d x d)`,
- `G_B = grad(B) in R^(d x d)`.

The equal-access conventional rival is permitted to construct the complete bilinear coordinate basis from the same state:

`Phi(z) = { (G_u)_{ij} u_k, (G_u)_{ij} B_k, (G_B)_{ij} u_k, (G_B)_{ij} B_k }`

for all admissible indices `i,j,k`. No target, future state, extra sensor or hidden field is provided to RI001.

## Exact contraction identities

The RI001/MHD candidate operators are

`Q_uu_i = sum_j (G_u)_{ij} u_j`,

`Q_uB_i = sum_j (G_B)_{ij} u_j`,

`Q_Bu_i = sum_j (G_u)_{ij} B_j`,

and

`Q_induction_i = Q_Bu_i - Q_uB_i`

`= sum_j [(G_u)_{ij} B_j - (G_B)_{ij} u_j]`.

Every coordinate of every listed RI001 operator is therefore a fixed linear functional of `Phi(z)`.

Hence there exists a fixed linear map `L` such that

`R_RI001(z) = L Phi(z)`.

Consequently

`sigma(R_RI001) subseteq sigma(Phi)`

for the same observed state `z`.

## Negative Seal

Under an equal-access rival that already receives the complete bilinear basis `Phi`, appending `Q_uu`, `Q_uB`, `Q_Bu` or `Q_induction` cannot increase raw observable information. These features are exact contractions/reparameterizations of information already available to the rival.

Therefore:

`TARGET_NATIVE_OPERATOR_RECONSTRUCTIBLE != DISTINCT_INFORMATION_CREDIT`

`BILINEAR_PHYSICAL_MEANING != NEW_OBSERVABLE_INFORMATION`

`EXACT_CONTRACTION_OF_EQUAL_ACCESS_BASIS => ZERO_RAW_INFORMATION_NOVELTY_CREDIT`

This conclusion is algebraic and does not require empirical fitting.

## What survives

The Negative Seal does **not** establish that RI001 lacks value. It changes the admissible claim.

A source-faithful RI001 decomposition may still provide structural or algorithmic value if, under equal information and a frozen resource budget, it provides one or more of:

1. lower-dimensional sufficient representation for a specified task;
2. better sample efficiency;
3. better out-of-block generalization;
4. stronger invariance/equivariance under a preregistered symmetry group;
5. cleaner conservation/balance accounting;
6. more stable detection of generation versus transport regimes;
7. lower computational or statistical complexity at matched error.

Any such claim must be tested against equal-access rivals. It cannot be called information novelty.

## Next admissible experiment

`G4_10D_CANDIDATE = RI001_STRUCTURAL_COMPRESSION_TOURNAMENT`

Preregister a comparison in which all methods receive the same `u, B, G_u, G_B` state and the same development blocks. Compare:

- generic full bilinear basis;
- generic low-rank bilinear basis;
- RI001 source-faithful contracted basis;
- simple linear/raw-state controls.

Match parameter/latent budgets where meaningful and use blocked spatial/temporal evaluation. Only if RI001 survives development should any clean confirmatory holdout be allocated.

## Firewalls

`INFORMATION_NOVELTY != STRUCTURAL_VALUE`

`STRUCTURAL_VALUE != PREDICTIVE_SUPERIORITY`

`PHYSICAL_INTERPRETABILITY != EMPIRICAL_GAIN`

`NEGATIVE_INFORMATION_SEAL != RI001_SOURCE_FALSIFICATION`

`EXACT_ALGEBRAIC_REDUNDANCY != NO_ALGORITHMIC_UTILITY`

`DEVELOPMENT_SURVIVAL_REQUIRED_BEFORE_CLEAN_HOLDOUT`

## Claim ceiling

No predictive scoring was performed. No empirical performance credit is granted. No novelty is proved. No cross-domain validation is claimed. No conclusion changes the PPAR–NS proof status or the Navier–Stokes global-regularity problem.
