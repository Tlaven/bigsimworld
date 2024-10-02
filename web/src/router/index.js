// src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'  // 导入首页组件
import ResourceManagement from '../views/ResourceManagement.vue' // 导入关于页面组件
import NotFound from '../views/NotFound.vue' // 导入 404 页面组件
import AppLayout from '@/views/layout/AppLayout.vue'
import DistributionStatistics from '@/views/DistributionStatistics.vue'



  // 定义路由
  const routes = [
    {
      path: '/',
      name: 'AppLayout',
      component: AppLayout,
      children: [
        {
          path: 'home',
          name: 'Home',
          component: Home
        },
        {
          path: 'ResourceManagement',
          name: 'ResourceManagement',
          component: ResourceManagement
        },
        {
          path: 'DistributionStatistics',
          name: 'DistributionStatistics',
          component: DistributionStatistics
        },

      ]
    },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(), // 使用 HTML5 的历史模式
  routes, // 注册定义的路由
})

// 导出 router 实例
export default router
