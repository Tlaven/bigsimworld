<template>
  <div ref="chart" style="width: 100%; height: 320px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from 'vue';
import * as echarts from 'echarts';

// sseData.simulation_load 为每步引擎耗时（秒），sseData.time 为世界时间。
// 只保留最近 60 个 tick 的内存滑动窗口，不写入 localStorage。
const sseData = inject('sseData');

const chart = ref(null);
let instance = null;

const MAX_POINTS = 60;
const times = [];
const loads = [];

// 清理旧版本残留在 localStorage 的历史数据
['localData', 'timestamps'].forEach((key) => localStorage.removeItem(key));

const initChart = () => {
  instance = echarts.init(chart.value);
  instance.setOption({
    title: { text: '每步引擎耗时（负载）' },
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: [], show: false },
    yAxis: { type: 'value', axisLabel: { formatter: (v) => `${Math.round(v * 1000)}ms` } },
    series: [{ name: 'Load', type: 'line', data: [], smooth: true, symbol: 'none' }],
  });
  window.addEventListener('resize', resize);
};

const pushPoint = (time, load) => {
  times.push(time);
  loads.push(load);
  if (times.length > MAX_POINTS) {
    times.shift();
    loads.shift();
  }
  instance?.setOption({
    xAxis: { data: [...times] },
    series: [{ data: [...loads] }],
  });
};

let lastTime = null;
const syncFromSse = (value) => {
  if (!value || typeof value.simulation_load !== 'number') return;
  if (value.time === lastTime) return; // 同一 tick 的重复推送去重
  lastTime = value.time;
  pushPoint(value.time || '', value.simulation_load);
};

watch(sseData, syncFromSse, { deep: true });

const resize = () => instance?.resize();

onMounted(initChart);

onUnmounted(() => {
  window.removeEventListener('resize', resize);
  instance?.dispose();
});
</script>
