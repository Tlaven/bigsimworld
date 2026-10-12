<template>
  <v-container fluid>
    <h1 class="text-h5 mb-2">显名与注意（分辨率层）</h1>
    <p class="text-body-2 text-medium-emphasis">
      少数被"注视"的家团/个体保持高分辨率（独立演算 + 生命轨迹），其余随注意力衰减溶回匿名统计。
      θ 为基线水位（低于即粗化），ρ 为已遗忘的近似量。
    </p>

    <v-row dense class="mb-2">
      <v-col v-for="card in cards" :key="card.label" cols="6" sm="4" md="2">
        <v-card variant="flat" class="py-3 text-center">
          <div class="text-caption text-medium-emphasis">{{ card.label }}</div>
          <div class="text-h6 font-weight-bold">{{ card.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-row dense>
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="text-subtitle-1">
            显名者（resolved）
            <span class="text-caption text-medium-emphasis">（{{ notables.length }}）</span>
          </v-card-title>
          <v-card-text style="max-height: 45vh; overflow-y: auto;">
            <div v-if="!notables.length" class="text-caption text-medium-emphasis">
              暂无——世界尚未点亮任何个体（无人注视，注意力即衰减）
            </div>
            <v-table v-else density="compact">
              <thead>
                <tr><th>姓名</th><th>年龄</th><th>财富</th><th>注意</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="person in notables" :key="person.id" style="cursor: pointer" @click="select(person)">
                  <td>{{ person.name }}</td>
                  <td>{{ person.age }}</td>
                  <td>{{ Math.round(person.wealth) }}</td>
                  <td>{{ person.attention }}</td>
                  <td>
                    <v-btn size="x-small" variant="text" @click.stop="pin(person)">关注</v-btn>
                    <v-btn size="x-small" variant="text" @click.stop="unpin(person)">放掉</v-btn>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="text-subtitle-1">
            生命轨迹 <span v-if="selected" class="text-caption">（{{ selected.name }}）</span>
          </v-card-title>
          <v-card-text>
            <div ref="chart" style="width: 100%; height: 240px;"></div>
            <div v-if="!selected" class="text-caption text-medium-emphasis">点选上方显名者查看其个体轨迹</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row dense class="mt-1">
      <v-col cols="12">
        <v-card>
          <v-card-title class="text-subtitle-1">团（clusters）</v-card-title>
          <v-card-text style="max-height: 40vh; overflow-y: auto;">
            <div v-if="!clusters.length" class="text-caption text-medium-emphasis">暂无团</div>
            <v-table v-else density="compact">
              <thead>
                <tr><th>id</th><th>状态</th><th>规模</th><th>ρ</th><th>注意</th></tr>
              </thead>
              <tbody>
                <tr v-for="cluster in clusters" :key="cluster.id">
                  <td>{{ cluster.id }}</td>
                  <td>{{ cluster.level === 1 ? '个体' : '聚合' }}</td>
                  <td>{{ cluster.size }}</td>
                  <td>{{ cluster.rho }}</td>
                  <td>{{ cluster.attention }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted, onUnmounted } from 'vue';
import echarts from '@/services/echarts';
import { setAttention, fetchLife } from '@/services/apiService';

const sseData = inject('sseData');
const resolution = computed(() => sseData.value?.resolution || null);
const notables = computed(() => sseData.value?.notables || []);
const clusters = computed(() => resolution.value?.clusters || []);

const selected = ref(null);
const chart = ref(null);
let instance = null;

const cards = computed(() => {
  const data = resolution.value || {};
  return [
    { label: '基线水位 θ', value: data.theta_base ?? '--' },
    { label: '叶子预算', value: data.budget_leaves ?? '--' },
    { label: '团数', value: data.cluster_count ?? '--' },
    { label: '个体数', value: data.resolved_count ?? '--' },
    { label: 'ρ（已遗忘）', value: data.rho ?? '--' },
  ];
});

const resize = () => instance?.resize();

const renderLife = async (personId) => {
  const data = await fetchLife(personId);
  if (!data || !data.life || !instance) return;
  instance.setOption({
    title: { text: '财富 / 好友数', textStyle: { fontSize: 12 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['财富', '好友'], top: 0, right: 0 },
    grid: { left: 8, right: 8, bottom: 8, top: 32, containLabel: true },
    xAxis: { type: 'category', data: data.life.map((point) => point.tick), show: false },
    yAxis: { type: 'value' },
    series: [
      { name: '财富', type: 'line', data: data.life.map((point) => point.wealth), smooth: true, symbol: 'none' },
      { name: '好友', type: 'line', data: data.life.map((point) => point.friends), smooth: true, symbol: 'none' },
    ],
  });
};

const select = (person) => {
  selected.value = person;
  renderLife(person.id);
};

const pin = (person) => setAttention({ personId: person.id, value: 1.0 });
const unpin = (person) => setAttention({ personId: person.id, value: 0.0 });

// 选中者若仍在续跑，随世界时间刷新其轨迹
watch(() => sseData.value?.time, () => {
  if (selected.value) renderLife(selected.value.id);
});

onMounted(() => {
  if (chart.value) {
    instance = echarts.init(chart.value);
    window.addEventListener('resize', resize);
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', resize);
  instance?.dispose();
});
</script>
