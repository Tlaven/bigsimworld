<template>
  <!-- Right Navigation Drawer -->
  <v-navigation-drawer app location="right" permanent width="320px">
    <v-list>
      <v-list-item title="实时世界" prepend-icon="mdi-earth"></v-list-item>
      <PeopleList max-height="70vh" />
    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import PeopleList from '@/components/PeopleList.vue';
</script>
