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
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, inject, nextTick } from 'vue';
import * as echarts from 'echarts';

// 使用 inject 获取全局提供的 sseData（由 SSE 实时更新）
const sseData = inject('sseData');

const ageChart = ref(null);
const wealthChart = ref(null);
let ageInstance = null;
let wealthInstance = null;

const ageOption = (data) => ({
  title: { text: 'Age Distribution' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: { type: 'value', boundaryGap: [0, 0.01] },
  yAxis: { type: 'category', data: data[0] },
  series: [{ name: 'Population', type: 'bar', data: data[1], itemStyle: { color: '#42a5f5' } }],
});

const wealthOption = (data) => ({
  title: { text: 'Wealth Distribution' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: { type: 'category', data: data[0] },
  yAxis: { type: 'value' },
  series: [{ name: 'Population', type: 'bar', data: data[1], itemStyle: { color: '#66bb6a' } }],
});

// 用 setOption(..., true) 原地更新，避免重复 init 泄漏实例
const render = () => {
  const data = sseData.value || {};
  if (ageInstance && data.age) ageInstance.setOption(ageOption(data.age), true);
  if (wealthInstance && data.wealth) wealthInstance.setOption(wealthOption(data.wealth), true);
};

const resize = () => {
  ageInstance?.resize();
  wealthInstance?.resize();
};

onMounted(async () => {
  await nextTick();
  ageInstance = echarts.init(ageChart.value);
  wealthInstance = echarts.init(wealthChart.value);
  render();
  window.addEventListener('resize', resize);
});

onUnmounted(() => {
  window.removeEventListener('resize', resize);
  ageInstance?.dispose();
  wealthInstance?.dispose();
});

// SSE 数据每 tick 更新 -> 图表实时刷新
watch(sseData, render, { deep: true });
</script>

<style scoped>
.v-card {
  height: 350px;
}

.text-h6 {
  font-weight: bold;
}
</style>
