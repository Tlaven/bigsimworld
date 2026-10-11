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


def gini_weighted(values, weights):
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    total = w.sum()
    if total == 0:
        return 0.0
    num = np.sum(w[:, None] * w[None, :] * np.abs(v[:, None] - v[None, :]))
    den = 2.0 * total * np.sum(w * v)
    return float(num / den) if den > 0 else 0.0


def _weighted_quantile(values, weights, quantiles):
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    order = np.argsort(v)
    v, w = v[order], w[order]
    cum = np.cumsum(w)
    cum /= cum[-1]
    return np.interp(quantiles, cum, v).round(3).tolist()


def measure_fingerprint(measure, space):
    age_hist = [0] * (len(AGE_BOUNDARIES) + 1)
    age_sum = 0.0
    pop = 0.0
    wealth_by_bucket = {}
    for index in measure.occupied:
        count = measure.counts[index]
        if count <= 0:
            continue
        age, gender, wealth_bucket, marital = space.decode(index)
        age_hist[np.digitize([age], AGE_BOUNDARIES)[0]] += count
        age_sum += age * count
        wealth_by_bucket[wealth_bucket] = wealth_by_bucket.get(wealth_bucket, 0.0) + count
        pop += count

    buckets = sorted(wealth_by_bucket)
    values = [space.wealth_value(b) for b in buckets]
    weights = [wealth_by_bucket[b] for b in buckets]
    quantiles = _weighted_quantile(values, weights, np.linspace(0, 1, 21)) if buckets else []
    total_wealth = float(sum(v * w for v, w in zip(values, weights)))

    return {
        "population": int(round(pop)),
        "total_wealth": round(total_wealth, 3),
        "age_hist": [int(round(x)) for x in age_hist],
        "wealth_quantiles": quantiles,
        "degree_hist": [int(round(pop))] if pop else [0],
        "gini_wealth": round(gini_weighted(values, weights), 5) if buckets else 0.0,
        "mean_age": round(age_sum / pop, 3) if pop else 0.0,
    }



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
