"""从测度直接生成展示用分布（O(占用桶数)，替代对个体的 O(N) 扫描）。"""

import numpy as np

AGE_BOUNDARIES = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
AGE_LABELS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
              "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84",
              "85-89", "90-94", "95-99", "100+"]


def measure_survey(measure, space, wealth_bins=20, wealth_width=50000.0):
    """返回 {'age': [labels, counts], 'wealth': [labels, counts]}（计数取整）。"""
    age_counts = np.zeros(len(AGE_BOUNDARIES) + 1)
    wealth_counts = np.zeros(wealth_bins + 1)  # 最后一桶为溢出
    for index in measure.occupied:
        count = measure.counts[index]
        if count <= 0:
            continue
        age, gender, wealth_bucket, marital = space.decode(index)
        age_counts[np.digitize([age], AGE_BOUNDARIES)[0]] += count
        value = space.wealth_value(wealth_bucket)
        wealth_counts[min(int(value / wealth_width), wealth_bins)] += count

    wealth_labels = [
        f"{int(i * wealth_width // 1000)}k-{int((i + 1) * wealth_width // 1000)}k"
        for i in range(wealth_bins)
    ] + [f"{int(wealth_bins * wealth_width // 1000)}k+"]

    return {
        "age": [AGE_LABELS, [int(round(x)) for x in age_counts]],
        "wealth": [wealth_labels, [int(round(x)) for x in wealth_counts]],
    }
