<template>
  <v-card>
    <v-card-title class="text-subtitle-1">
      活人窗口
      <span class="text-caption text-medium-emphasis">（{{ people.length }} 个真个体）</span>
    </v-card-title>
    <v-card-subtitle v-if="time" class="text-caption">世界时间 {{ time }}</v-card-subtitle>
    <v-card-text :style="{ maxHeight: maxHeight, overflowY: 'auto' }">
      <div v-if="!people.length" class="text-caption text-medium-emphasis">
        Waiting for data...
      </div>
      <v-table v-else density="compact">
        <thead>
          <tr>
            <th>姓名</th>
            <th>性别</th>
            <th>年龄</th>
            <th>财富</th>
            <th>好友</th>
            <th>婚配</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="person in people" :key="person.atr[0]">
            <td>{{ person.atr[1] }}</td>
            <td>{{ person.atr[2] === 'male' ? '男' : '女' }}</td>
            <td>{{ person.atr[3] }}</td>
            <td>{{ Math.round(person.atr[4]) }}</td>
            <td>{{ friends(person) }}</td>
            <td>{{ spouse(person) }}</td>
          </tr>
        </tbody>
      </v-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, inject } from 'vue';

defineProps({ maxHeight: { type: String, default: '50vh' } });

// sseData.people 结构：[id, name, gender, age, wealth] + relationships[4] = [friend, spouse, parent, child]
const sseData = inject('sseData');
const people = computed(() => sseData.value?.people || []);
const time = computed(() => sseData.value?.time || '');

const friends = (person) => (person.relationships?.[0] || []).length;
const spouse = (person) => ((person.relationships?.[1] || []).length ? '已婚' : '单身');
</script>
