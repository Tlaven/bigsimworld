<template>
  <v-app>
    <v-container fluid>
      <v-row>
        <v-col cols="12">
          <v-card>
            <v-card-title class="text-h5">Resource Management</v-card-title>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="8">
          <v-card style="height: 400px;"> <!-- 设置高度 -->
            <v-card-text>
              <ChartComponent ref="chart" />
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="4">
          <v-card style="height: 400px;"> <!-- 设置高度 -->
            <v-card-title>Resource Information</v-card-title>
            <v-card-text>
              <p>这里可以放置关于资源的其他信息。</p>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
        <v-col cols="8">
          <v-card style="height: 400px;"> <!-- 设置高度 -->
            <v-card-title>Current Data</v-card-title>
            <v-card-text>
              <CurrentDataComponent />
            </v-card-text>
          </v-card>
        </v-col>
    </v-container>
  </v-app>
</template>

<script setup>
import ChartComponent from '@/components/SimulationLoadChart.vue'; // 导入你的图表组件
import CurrentDataComponent from '@/components/CurrentData'; // 导入当前数据
</script>

<style scoped>
/* 自定义样式（如有需要） */
</style>
