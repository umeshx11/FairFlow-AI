# Fairness Definitions

This note formalizes the core fairness metrics used by FairLens AI.

## Notation
- `\hat{Y}`: model prediction (`1` = positive decision, `0` = negative decision)
- `D`: protected attribute group indicator
- `D=unprivileged`: protected subgroup under analysis
- `D=privileged`: reference subgroup

## Disparate Impact (DI)

\[
\mathrm{DI} = \frac{P(\hat{Y}=1 \mid D=\mathrm{unprivileged})}{P(\hat{Y}=1 \mid D=\mathrm{privileged})}
\]

Interpretation:
- `DI = 1.0` indicates equal selection rates.
- `DI < 0.8` typically violates the 80% rule used in hiring fairness governance.

## Statistical Parity Difference (SPD)

\[
\mathrm{SPD} = P(\hat{Y}=1 \mid D=\mathrm{unprivileged}) - P(\hat{Y}=1 \mid D=\mathrm{privileged})
\]

Interpretation:
- `SPD = 0` indicates parity.
- Larger absolute values imply stronger group-level disparity.

## Equal Opportunity Difference (EOD)

\[
\mathrm{EOD} = \mathrm{TPR}_{unprivileged} - \mathrm{TPR}_{privileged}
\]

where `TPR = P(\hat{Y}=1 \mid Y=1, D=group)`.

## Average Odds Difference (AOD)

\[
\mathrm{AOD} = \frac{1}{2}\left[(\mathrm{FPR}_{unprivileged} - \mathrm{FPR}_{privileged}) + (\mathrm{TPR}_{unprivileged} - \mathrm{TPR}_{privileged})\right]
\]

where `FPR = P(\hat{Y}=1 \mid Y=0, D=group)`.

## FairLens Policy Thresholds
- `DI > 0.80`
- `|SPD| < 0.10`
- `|EOD| < 0.10`
- `|AOD| < 0.10`

These thresholds are encoded in the backend policy checks and mapped to the dashboard pass/fail indicators.
