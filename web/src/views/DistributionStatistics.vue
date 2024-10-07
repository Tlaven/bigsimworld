<template>
  <v-row>
    <!-- 年龄分布图表 -->
    <v-col cols="12" md="6">
      <v-card>
        <v-card-title class="text-h6">Age Distribution</v-card-title>
        <v-card-text>
          <div ref="ageChart" style="width: 100%; height: 300px;"></div>
        </v-card-text>
      </v-card>
    </v-col>

    <!-- 财富分布图表 -->
    <v-col cols="12" md="6">
      <v-card>
        <v-card-title class="text-h6">Wealth Distribution</v-card-title>
        <v-card-text>
          <div ref="wealthChart" style="width: 100%; height: 300px;"></div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>

  <v-row>
    <!-- 其他信息图表 -->
    <v-col cols="12" md="8">
      <v-card>
        <v-card-title class="text-h6">Additional Information</v-card-title>
        <v-card-text>
          <div ref="additionalInfoChart" style="width: 100%; height: 200px;"></div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue';
import * as echarts from 'echarts';

// 使用 inject 获取全局提供的 sseData
const sseData = inject('sseData');

const ageChart = ref(null);
const wealthChart = ref(null);
const additionalInfoChart = ref(null);

// 初始化 ECharts 图表
const initChart = (chartRef, options) => {
  const chartInstance = echarts.init(chartRef);
  chartInstance.setOption(options);
  return chartInstance;
};

// 更新年龄分布图表
const updateAgeChart = () => {
  const ageData = sseData.value.age; // Access age data
  const options = {
    title: {
      text: 'Age Distribution',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      boundaryGap: [0, 0.01],
    },
    yAxis: {
      type: 'category',
      data: ageData[0], // Get age groups from the first array
    },
    series: [
      {
        name: 'Population',
        type: 'bar',
        data: ageData[1], // Get corresponding values from the second array
        itemStyle: {
          color: '#42a5f5', // 选择适合的颜色
        },
      },
    ],
  };
  return initChart(ageChart.value, options);
};

// 更新财富分布图表
const updateWealthChart = () => {
  const wealthData = sseData.value.wealth; // Access wealth data
  const options = {
    title: {
      text: 'Wealth Distribution',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category', // Change to 'category' for wealth ranges
      data: wealthData[0], // Get wealth ranges from the first array
    },
    yAxis: {
      type: 'value', // Value axis for counts
    },
    series: [
      {
        name: 'Population',
        type: 'bar', // Changed to line chart
        data: wealthData[1], // Get corresponding values from the second array
        itemStyle: {
          color: '#66bb6a', // 选择适合的颜色
        },
        smooth: true, // Makes the line smooth
      },
    ],
  };
  return initChart(wealthChart.value, options);
};

// 挂载时初始化图表
onMounted(() => {
  if (sseData.value) {
    updateAgeChart();
    updateWealthChart();
  }
});
</script>

<style scoped>
/* 可选：自定义样式 */
.v-card {
  height: 350px; /* 设定卡片高度 */
}

.text-h6 {
  font-weight: bold; /* 使标题更突出 */
}
</style>
