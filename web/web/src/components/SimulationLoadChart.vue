<template>
    <div ref="chart" style="width: 100%; height: 400px;"></div>
  </template>
  
  <script setup>
  import { ref, onMounted, onUnmounted, watch, computed, inject } from 'vue';
  import * as echarts from 'echarts';

  // 使用 inject 获取全局提供的 sseData 和 error
  const sseData = inject('sseData');
  
  const chart = ref(null);
  const chartInstance = ref(null);
  
  // 计算属性：返回持久化的 SSE 数据中最新的 simulation_load 数组
  const currentData = computed(() => {
    return sseData.value.length > 0
      ? sseData.value.map(item => item.simulation_load)
      : [];
  });
  
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
          data: currentData.value, // 使用 currentData
          smooth: true,
          symbol: 'none', // 不显示数据点
        },
      ],
    };
    chartInstance.value.setOption(options);
  };
  
  // 更新图表数据
  const updateChart = () => {
    if (sseData.value.length > 0) {
      const timestamps = sseData.value.map(item => item.timestamp); // 假设有 timestamp 字段
  
      chartInstance.value.setOption({
        xAxis: {
          data: timestamps,
        },
        series: [
          {
            name: 'Load',
            data: currentData.value, // 更新为 currentData
          },
        ],
      });
    }
  };
  
  // 监听 SSE 数据的变化
  watch(sseData, updateChart);
  
  onMounted(() => {
    initChart();
  });
  
  onUnmounted(() => {
    if (chartInstance.value) {
      chartInstance.value.dispose(); // 清理实例
    }
  });
  </script>
  
  <style scoped>
  /* 自定义样式 */
  </style>
  