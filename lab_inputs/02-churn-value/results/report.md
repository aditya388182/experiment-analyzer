# Churn and customer value: results

UCI Online Retail II: 1,067,371 transaction rows, 5,878 customers, 2009-12-01 to 2011-12-09.
Cleaning: 824,364 rows with a customer ID, 797,885 after removing exact duplicates, 18,390 cancellation rows set aside, 779,425 purchase rows kept.

## 1. Snapshots (churn = no purchase in the next 90 days)

| Snapshot | Role | Customers | Churn rate |
|---|---|---|---|
| 2010-09-01 | train | 3,321 | 41.9% |
| 2010-12-01 | train | 4,266 | 66.9% |
| 2011-03-01 | train | 4,276 | 63.2% |
| 2011-06-01 | train | 4,338 | 63.4% |
| 2011-09-01 | test | 4,335 | 50.5% |

## 2. Model comparison

| Model | Validation ROC AUC | Test ROC AUC | Test PR AUC |
|---|---|---|---|
| recency_rule | 0.747 | 0.709 | 0.682 |
| rfm_logistic | 0.797 | 0.760 | 0.728 |
| gradient_boosting (selected) | 0.803 | 0.769 | 0.736 |

Selected model on the test snapshot: ROC AUC 0.769 (95% CI 0.756 to 0.784), PR AUC 0.736 (0.716 to 0.758), Brier 0.207, calibration error 11.5%.
Gain over the recency rule: 0.050 to 0.071 AUC (95% CI). Shuffled scores give AUC 0.500.

Predicted vs observed churn by risk decile (highest risk first): 88%/79%, 84%/75%, 81%/72%, 78%/67%, 74%/62%, 67%/49%, 58%/44%, 48%/33%, 33%/18%, 10%/6%.

## 3. Revenue at risk

- 2,189 customers churned; they had spent 1,754,077 GBP in the prior year (21.2% of all prior-year revenue).
- Contacting the top 20% ranked by churn risk x customer value reaches 51% of that revenue (value only: 40%; risk only: 17%; random: 20%).
- The top 20% by risk alone contains 30% of all churners.

## 4. Customer value (next 90 days of revenue)

- Top 10% by predicted value holds 56% of actual next-90-day revenue (ranking by last-year revenue: 58%; by last-90-day revenue: 55%).
- Rank correlation with actual revenue: model 0.56, last-year revenue 0.54.

## 5. Repeat purchase (Kaplan-Meier)

- Of 4,166 new customers (1,435 censored), 21% reorder within 30 days, 43% reorder within 90 days, 58% reorder within 180 days, 69% reorder within 365 days.
