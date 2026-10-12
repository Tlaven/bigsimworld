// src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/views/layout/AppLayout.vue'
import DistributionStatistics from '@/views/DistributionStatistics.vue'
import RoleInformation from '@/views/RoleInformation.vue'
import NotFound from '../views/NotFound.vue' // 404 页面组件

// 定义路由
const routes = [
  {
    path: '/',
    name: 'AppLayout',
    component: AppLayout,
    children: [
      {
        path: '',
        redirect: { name: 'WorldOverview' }
      },
      {
        path: 'world-overview',
        name: 'WorldOverview',
        component: () => import('@/views/WorldOverview.vue')
      },
      {
        path: 'distribution-statistics',
        name: 'DistributionStatistics',
        component: DistributionStatistics
      },
      {
        path: 'role-information',
        name: 'RoleInformation',
        component: RoleInformation
      },
      {
        path: 'resolution',
        name: 'ResolutionView',
        component: () => import('@/views/ResolutionView.vue')
      }
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
