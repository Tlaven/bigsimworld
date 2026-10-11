"""个体/测度引擎的"分布指纹"——用于收敛对比的归一化度量。"""

import numpy as np

AGE_BOUNDARIES = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]


def gini(values):
    x = np.sort(np.asarray(values, dtype=np.float64))
    n = x.size
    total = x.sum()
    if n == 0 or total == 0:
        return 0.0
    cum = np.cumsum(x)
    return float((n + 1 - 2 * cum.sum() / total) / n)


def fingerprint(engine):
    chars = list(engine.characters.values())
    n = len(chars)
    if n == 0:
        return {
            "population": 0,
            "total_wealth": 0.0,
            "age_hist": [0] * (len(AGE_BOUNDARIES) + 1),
            "wealth_quantiles": [],
            "degree_hist": [0],
            "gini_wealth": 0.0,
            "mean_age": 0.0,
        }

    ages = np.array([c.age for c in chars], dtype=np.int64)
    wealths = np.array([c.wealth for c in chars], dtype=np.float64)
    degrees = np.array([len(c.relatives) for c in chars], dtype=np.int64)

    return {
        "population": n,
        "total_wealth": round(float(wealths.sum()), 3),
        "age_hist": np.bincount(
            np.digitize(ages, AGE_BOUNDARIES), minlength=len(AGE_BOUNDARIES) + 1
        ).tolist(),
        "wealth_quantiles": np.quantile(wealths, np.linspace(0, 1, 21)).round(3).tolist(),
        "degree_hist": np.bincount(degrees, minlength=int(degrees.max()) + 1).tolist(),
        "gini_wealth": round(gini(wealths), 5),
        "mean_age": round(float(ages.mean()), 3),
    }
