
def Wealth_distribution_statistics(data):
    # 提取wealth值并进行统计
    wealth_values = []

    for item in data['individual_list']:
        # 从wealth字符串中提取wealth值并转换为整数
        #wealth_str = item['wealth'].split(': ')[1]
        wealth_values.append(int(item['wealth']))

    # 计算总和、平均值、最大值、最小值
    # total_wealth = sum(wealth_values)
    # average_wealth = total_wealth / len(wealth_values)
    # max_wealth = max(wealth_values)
    # min_wealth = min(wealth_values)

    # 打印基本统计信息
    # print(f"Total Wealth: {total_wealth}")
    # print(f"Average Wealth: {average_wealth:.2f}")
    # print(f"Max Wealth: {max_wealth}")
    # print(f"Min Wealth: {min_wealth}")

    # 财富分布统计
    # 定义财富区间
    intervals = [(0, 20000), (20001, 40000), (40001, 60000), (60001, 80000), (80001, 100000), (100001, float('inf'))]
    distribution = {f"{interval[0]}-{interval[1]}": 0 for interval in intervals}

    # 统计每个区间的频数
    for wealth in wealth_values:
        for interval in intervals:
            if interval[0] <= wealth <= interval[1]:
                distribution[f"{interval[0]}-{interval[1]}"] += 1
                break

    # 打印分布情况
    # print("Wealth Distribution:")
    # for interval, count in distribution.items():
    #     print(f"{interval}: {count}")

    
    return distribution

if __name__ == "__main__":
    data={'individual_list': [{'title': '司红兵', 'description': ' Age: 33, Gender: 男', 'wealth': 73328}, {'title': '黎怀东', 'description': ' Age: 35, Gender: 女', 'wealth': 59512}, {'title': '舒燕鹏', 'description': ' Age: 50, Gender: 男', 'wealth': 71911}, {'title': '麻楚煊', 'description': ' Age: 56, Gender: 女', 'wealth': 63443}, {'title': '苏沁韵', 'description': ' Age: 18, Gender: 男', 'wealth': 75493}, {'title': '茹晓欢', 'description': ' Age: 31, Gender: 男', 'wealth': 47315}, {'title': '白彩芬', 'description': ' Age: 70, Gender: 女', 'wealth': 60478}, {'title': '纪艺含', 'description': ' Age: 73, Gender: 女', 'wealth': 68914}, {'title': '曹仁', 'description': ' Age: 78, Gender: 女', 'wealth': 53145}, {'title': '于广玉', 'description': ' Age: 20, Gender: 女', 'wealth': 48237}, {'title': '杨铁成', 'description': ' Age: 65, Gender: 男', 'wealth': 46566}, {'title': '蒋梓城', 'description': ' Age: 26, Gender: 女', 'wealth': 18369}, {'title': '欧欣汝', 'description': ' Age: 77, Gender: 女', 'wealth': 64665}, {'title': '仲紫翰', 'description': ' Age: 69, Gender: 女', 'wealth': 60508}, {'title': '乜建成', 'description': ' Age: 75, Gender: 男', 'wealth': 31136}, {'title': '章全', 'description': ' Age: 55, Gender: 男', 'wealth': 57619}, {'title': '钱莺罂', 'description': ' Age: 76, Gender: 男', 'wealth': 62792}, {'title': '辛厚湘', 'description': ' Age: 30, Gender: 女', 'wealth': 25058}, {'title': '蒙琰萍', 'description': ' Age: 55, Gender: 男', 'wealth': 33344}, {'title': '梅雨杰', 'description': ' Age: 52, Gender: 男', 'wealth': 20400}]}
    print(Wealth_distribution_statistics(data))