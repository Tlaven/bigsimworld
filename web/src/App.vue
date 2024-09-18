<template>
  <div id="app">
    <TimeDisplay />
  </div>
</template>

<script>
import TimeDisplay from './components/TimeDisplay.vue';

export default {
  name: 'App',
  components: {
    TimeDisplay,
  },
};
</script>

<style>
/* 全局样式可以放在这里 */
</style>
