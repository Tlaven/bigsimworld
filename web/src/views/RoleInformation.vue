<template>
  <div>
    <h1 class="text-h5 mb-4">角色信息（活人窗口）</h1>
    <p class="text-body-2 text-medium-emphasis">
      以下是在"分布为主体"的世界里被物化的{{ '' }}真个体：带有真实关系图（好友/配偶/父母/子女），
      由 SSE 实时推送。
    </p>
    <PeopleList max-height="70vh" />
  </div>
</template>

<script setup>
import PeopleList from '@/components/PeopleList.vue';
</script>
