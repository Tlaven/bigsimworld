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
          <tr v-for="person in people" :key="person.id">
            <td>{{ person.name }}</td>
            <td>{{ person.gender === 'male' ? '男' : '女' }}</td>
            <td>{{ person.age }}</td>
            <td>{{ Math.round(person.wealth) }}</td>
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

// sseData.people：{id, name, gender, age, wealth, relationships{friend,spouse,parent,child}}
// relationships 每组为 [id, name] 对的数组
const sseData = inject('sseData');
const people = computed(() => sseData.value?.people || []);
const time = computed(() => sseData.value?.time || '');

const friends = (person) => (person.relationships?.friend || []).length;
const spouse = (person) => ((person.relationships?.spouse || []).length ? '已婚' : '单身');
</script>
