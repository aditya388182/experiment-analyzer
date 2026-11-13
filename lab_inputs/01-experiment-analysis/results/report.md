# Email experiment: results

Hillstrom MineThatData challenge: 64,000 customers randomized to a men's email, a women's email, or no email.

## 1. Is the experiment valid?
- Arm sizes [21307, 21387, 21306] vs a planned 1/3 split: SRM p = 0.90 (no mismatch).
- Largest pre-experiment covariate imbalance: 0.012 standardized mean difference (under 0.1 is balanced).
- A/A test: 2000 random splits of the control arm flagged 4.5% at alpha 0.05 (should be about 5%).
- Power: with 21,306 per arm, smallest detectable lift is 0.84% points on visits and 0.20% points on conversion.

## 2. Did the emails work? (vs no email, 95% CI, Holm-adjusted p)

| Arm | Metric | Email | Control | Lift | 95% CI | Relative | p (Holm) |
|---|---|---|---|---|---|---|---|
| mens | visit rate | 18.28% | 10.62% | 7.66% pts | 7.00% to 8.32% | 72% | 8e-112 |
| mens | conversion rate | 1.25% | 0.57% | 0.68% pts | 0.50% to 0.86% | 119% | 6e-13 |
| mens | spend per customer | $1.42 | $0.65 | $0.77 | $0.50 to $1.06 (bootstrap) | 118% | 3e-07 |
| womens | visit rate | 15.14% | 10.62% | 4.52% pts | 3.89% to 5.16% | 43% | 1e-43 |
| womens | conversion rate | 0.88% | 0.57% | 0.31% pts | 0.15% to 0.47% | 54% | 0.0003 |
| womens | spend per customer | $1.08 | $0.65 | $0.42 | $0.17 to $0.70 (bootstrap) | 65% | 0.001 |

Men's vs women's email on visits: 3.14% points (2.43% to 3.84%), p = 4e-18.

## 3. Variance reduction

- mens_visit: correlation with prior-year spend 0.067; CUPED removes 0.44% of variance; regression adjustment on all covariates removes 2.9%.
- mens_spend: correlation with prior-year spend 0.021; CUPED removes 0.04% of variance; regression adjustment on all covariates removes 0.2%.
- womens_visit: correlation with prior-year spend 0.063; CUPED removes 0.40% of variance; regression adjustment on all covariates removes 2.8%.
- womens_spend: correlation with prior-year spend 0.020; CUPED removes 0.04% of variance; regression adjustment on all covariates removes -0.1%.

## 4. Who should get the email? (uplift model on visits, 30% holdout)

### mens email
- Model chosen by 5-fold CV on training data: s_learner_logistic (CV Qini 0.019).
- Holdout Qini -0.001 (95% bootstrap CI -0.048 to 0.045; shuffled scores give 0.000).
- Targeting the top 30% captures 31% of incremental visits (random: 30%); top 50% captures 51%.
- Observed uplift by predicted quintile, best to worst: 8.9% | 6.6% | 6.4% | 8.0% | 9.1% (average 7.7%).

### womens email
- Model chosen by 5-fold CV on training data: t_learner_gradient_boosting (CV Qini 0.126).
- Holdout Qini 0.118 (95% bootstrap CI 0.042 to 0.197; shuffled scores give -0.001).
- Targeting the top 30% captures 44% of incremental visits (random: 30%); top 50% captures 69%.
- Observed uplift by predicted quintile, best to worst: 7.9% | 5.4% | 5.1% | 1.9% | 2.3% (average 4.5%).

