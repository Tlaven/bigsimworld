<template>
  <div ref="chart" style="width: 100%; height: 400px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, inject } from 'vue';
import * as echarts from 'echarts';

// 使用 inject 获取全局提供的 sseData
const sseData = inject('sseData');

const chart = ref(null);
const chartInstance = ref(null);

// 本地保存的最多 60 条数据
const localData = ref(JSON.parse(localStorage.getItem('localData')) || []);  // 从 localStorage 加载
const timestamps = ref(JSON.parse(localStorage.getItem('timestamps')) || []); // 同样加载时间戳

// 初始化 ECharts 图表
const initChart = () => {
  chartInstance.value = echarts.init(chart.value);
  const options = {
    title: {
      text: 'Simulation Load Over Time',
    },
    tooltip: {
      trigger: 'axis',
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: [], // x 轴数据将在后面更新
      show: false, // 隐藏 x 轴
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
    },
    series: [
      {
        name: 'Load',
        type: 'line',
        data: [], // 初始化时无数据
        smooth: true,
        symbol: 'none', // 不显示数据点
      },
    ],
  };
  chartInstance.value.setOption(options);
  
  // 初始化时如果有缓存的数据，先显示它们
  if (localData.value.length > 0) {
    updateChart(); 
  }
};

// 更新图表数据
const updateChart = () => {
  if (sseData.value) {
    // 将新数据添加到本地数组中
    localData.value.push(sseData.value.simulation_load);
    timestamps.value.push(sseData.value.timestamp);  // 假设有时间戳字段

    // 只保留最近 60 条数据
    if (localData.value.length > 60) {
      localData.value.shift();
      timestamps.value.shift();
    }

    // 将数据保存到 localStorage 中
    localStorage.setItem('localData', JSON.stringify(localData.value));
    localStorage.setItem('timestamps', JSON.stringify(timestamps.value));

    // 更新图表数据
    chartInstance.value.setOption({
      xAxis: {
        data: timestamps.value, // 更新 x 轴的时间戳数据
      },
      series: [
        {
          name: 'Load',
          data: localData.value, // 更新为最新 60 条数据
        },
      ],
    });
  }
};

// 监听 SSE 数据的变化
watch(sseData, updateChart);

// 挂载时初始化图表
onMounted(() => {
  initChart();
});

// 卸载时清理图表实例
onUnmounted(() => {
  if (chartInstance.value) {
    chartInstance.value.dispose(); // 清理实例
  }
});
</script>

<style scoped>
/* 可选：自定义样式 */
</style>
