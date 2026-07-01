import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'
import { useUserStore } from '@/stores/user'
import { useAgentStore } from '@/stores/agent'
import { sanitizeRedirect } from '@/utils/oidcAutoStart'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'main',
      component: BlankLayout,
      children: [
        {
          path: '',
          name: 'Home',
          component: () => import('../views/HomeView.vue'),
          meta: { keepAlive: true, requiresAuth: false }
        }
      ]
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/auth/oidc/callback', // oidcĐăng nhập trang gọi lại
      name: 'OIDCCallback',
      component: () => import('@/views/OIDCCallbackView.vue'),
      meta: { public: true }
    },
    {
      path: '/auth/cli/authorize',
      name: 'CLIAuthAuthorize',
      component: () => import('@/views/CLIAuthAuthorizeView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/agent',
      name: 'AgentMain',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'AgentComp',
          component: () => import('../views/AgentView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        },
        {
          path: ':thread_id',
          name: 'AgentCompWithThreadId',
          component: () => import('../views/AgentView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        }
      ]
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'WorkspaceComp',
          component: () => import('../views/WorkspaceView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        }
      ]
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'DashboardComp',
          component: () => import('../views/DashboardView.vue'),
          meta: { keepAlive: false, requiresAuth: true, requiresSuperAdmin: true }
        }
      ]
    },
    {
      path: '/model-manage',
      name: 'model-manage',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ModelManageComp',
          component: () => import('../views/ModelManageView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
    {
      path: '/extensions',
      name: 'extensions',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ExtensionsComp',
          component: () => import('../views/ExtensionsView.vue'),
          meta: {
            keepAlive: false,
            requiresAuth: true
          },
          children: [
            {
              path: 'knowledgebase/:kbId',
              name: 'ExtensionKnowledgeBaseDetail',
              component: () => import('../views/DataBaseInfoView.vue'),
              meta: {
                keepAlive: false,
                requiresAuth: true,
                requiresAdmin: true
              }
            },
            {
              path: 'mcp/:slug',
              name: 'ExtensionMcpDetail',
              component: () => import('../components/extensions/McpDetailView.vue'),
              meta: {
                keepAlive: false,
                requiresAuth: true,
                requiresAdmin: true
              }
            },
            {
              path: 'skill/:slug',
              name: 'ExtensionSkillDetail',
              component: () => import('../components/extensions/SkillDetailView.vue'),
              meta: {
                keepAlive: false,
                requiresAuth: true
              }
            }
          ]
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('../views/EmptyView.vue'),
      meta: { requiresAuth: false }
    }
  ]
})

// Bảo vệ mặt trận toàn cầu
router.beforeEach(async (to) => {
  // Kiểm tra xem tuyến đường có yêu cầu xác thực không
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth === true)
  const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)
  const requiresSuperAdmin = to.matched.some((record) => record.meta.requiresSuperAdmin)

  const userStore = useUserStore()

  // nếu có token Nhưng thông tin người dùng không được tải，Lấy thông tin người dùng trước
  if (userStore.token && !userStore.userId) {
    try {
      await userStore.getCurrentUser()
    } catch (error) {
      // Nếu việc thu thập thông tin người dùng không thành công（Chẳng hạn như token Đã hết hạn），Xóa token
      console.error('Không thể lấy được thông tin người dùng:', error)
      userStore.logout()
    }
  }

  const isLoggedIn = userStore.isLoggedIn
  const isAdmin = userStore.isAdmin
  const isSuperAdmin = userStore.isSuperAdmin

  // Nếu tuyến đường yêu cầu xác thực nhưng người dùng chưa đăng nhập
  if (requiresAuth && !isLoggedIn) {
    // Lưu đường dẫn bạn đang cố truy cập，Nhảy sau khi đăng nhập
    sessionStorage.setItem('redirect', to.fullPath)
    return '/login'
  }

  // Nếu tuyến yêu cầu quyền quản trị viên nhưng người dùng không phải là quản trị viên
  if (requiresAdmin && !isAdmin) {
    // Nếu là người dùng bình thường，Chuyển đến trang trò chuyện trống
    try {
      const agentStore = useAgentStore()
      // chờ đã store Quá trình khởi tạo đã hoàn tất
      if (!agentStore.isInitialized) {
        await agentStore.initialize()
      }
      return '/agent'
    } catch (error) {
      console.error('Không thể lấy được thông tin đại lý:', error)
      return '/agent'
    }
  }

  // Nếu tuyến yêu cầu đặc quyền của quản trị viên cấp cao nhưng người dùng không phải là quản trị viên cấp cao
  if (requiresSuperAdmin && !isSuperAdmin) {
    try {
      const agentStore = useAgentStore()
      if (!agentStore.isInitialized) {
        await agentStore.initialize()
      }
      return '/agent'
    } catch (error) {
      console.error('Không thể lấy được thông tin đại lý:', error)
      return '/agent'
    }
  }

  // Nếu người dùng đã đăng nhập nhưng truy cập vào trang đăng nhập，nhấn redirect Nhảy tham số
  if (to.path === '/login' && isLoggedIn) {
    return sanitizeRedirect(to.query.redirect)
  }

  // Điều hướng bình thường trong các trường hợp khác
  return true
})

export default router
