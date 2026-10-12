<template>
  <v-container fluid class="world-overview">
    <v-row dense>
      <v-col v-for="card in cards" :key="card.label" cols="12" sm="6" md="4">
        <v-card class="py-4 text-center" variant="flat">
          <div class="text-caption text-medium-emphasis">{{ card.label }}</div>
          <div class="text-h5 font-weight-bold">{{ card.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-row dense>
      <v-col cols="12">
        <v-card>
          <v-card-text>
            <SimulationLoadChart />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { computed, inject } from 'vue';
import SimulationLoadChart from '@/components/SimulationLoadChart.vue';
import { sseStatus } from '@/services/sseService';

const sseData = inject('sseData');
const sseError = inject('sseError');

const statusLabel = {
  idle: '未连接',
  connecting: '连接中…',
  connected: '已连接',
  reconnecting: '重连中…',
  error: '连接失败',
};

const cards = computed(() => {
  const data = sseData.value || {};
  const load = typeof data.simulation_load === 'number'
    ? `${(data.simulation_load * 1000).toFixed(1)} ms`
    : '--';
  return [
    { label: '世界时间', value: data.time || '--' },
    { label: '总人口', value: data.population != null ? data.population.toLocaleString() : '--' },
    { label: '连接状态', value: statusLabel[sseStatus.value] || sseError.value || '--' },
    { label: '单步引擎耗时', value: load },
    { label: '好友边数（窗口内）', value: friendEdges.value },
    { label: '窗口真个体', value: data.people ? data.people.length : '--' },
  ];
});

const friendEdges = computed(() => {
  const people = sseData.value?.people || [];
  return people.reduce((acc, person) => acc + (person.relationships?.friend?.length || 0), 0);
});
</script>

<style scoped>
.world-overview {
  min-height: 70vh;
}
</style>
