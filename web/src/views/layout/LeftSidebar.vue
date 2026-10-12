<template>
  <v-navigation-drawer :width="160" app permanent>
    <!-- 应用标题部分 -->
    <v-list-item title="SimuWorld" subtitle="大世界仿真"></v-list-item>
    <v-divider></v-divider>

    <!-- 导航（Vuetify 3：prepend-icon） -->
    <v-list>
      <v-list-item
        :to="{ name: 'WorldOverview' }"
        title="世界总览"
        prepend-icon="mdi-earth"
        link
      />
      <v-list-item
        :to="{ name: 'DistributionStatistics' }"
        title="分布统计"
        prepend-icon="mdi-chart-bar"
        link
      />
      <v-list-item
        :to="{ name: 'RoleInformation' }"
        title="角色信息"
        prepend-icon="mdi-account-group"
        link
      />
      <v-list-item
        :to="{ name: 'ResolutionView' }"
        title="显名与注意"
        prepend-icon="mdi-eye"
        link
      />
    </v-list>
  </v-navigation-drawer>
</template>
