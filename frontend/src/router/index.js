import { createRouter, createWebHistory } from 'vue-router'

// 页面组件懒加载
const Login = () => import('../views/Login.vue')
const LiveMonitor = () => import('../views/LiveMonitor.vue')
const Events = () => import('../views/Events.vue')
const Faces = () => import('../views/Faces.vue')
const FaceManagement = () => import('../views/FaceManagement.vue')
const FaceRecognition = () => import('../views/FaceRecognition.vue')
const Zones = () => import('../views/Zones.vue')

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { title: '管理员登录', hideLayout: true }
  },
  {
    path: '/live',
    name: 'LiveMonitor',
    component: LiveMonitor,
    meta: { title: '实时监控' }
  },
  {
    path: '/events',
    name: 'Events',
    component: Events,
    meta: { title: '事件告警' }
  },
  {
    path: '/faces',
    name: 'Faces',
    component: Faces
  },
  {
    path: '/face-management',
    name: 'FaceManagement',
    component: FaceManagement
  },
  {
    path: '/face-recognition',
    name: 'FaceRecognition',
    component: FaceRecognition,
    meta: { title: '人脸识别' }
  },
  {
    path: '/zones',
    name: 'Zones',
    component: Zones,
    meta: { title: '危险区域' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 家庭视频监控系统`
  }
  next()
})

export default router 