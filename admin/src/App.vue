<script setup>
import { ref, h, onMounted, computed } from 'vue'
import { useRouter, useRoute, RouterView } from 'vue-router'
import {
  NConfigProvider, NMessageProvider, NDialogProvider, darkTheme,
  NLayout, NLayoutSider, NLayout as NLayoutContent, NMenu, NIcon, NButton, NSpin, NResult,
} from 'naive-ui'
import {
  GridOutline, CubeOutline, ReceiptOutline, CartOutline,
  SettingsOutline, LogOutOutline, RocketOutline,
} from '@vicons/ionicons5'
import { navyThemeOverrides } from './theme'
import { api, setUnauthorizedHandler } from './api'

const router = useRouter()
const route = useRoute()

const checking = ref(true)
const authed = ref(false)

function icon(comp) {
  return () => h(NIcon, null, { default: () => h(comp) })
}

const menuOptions = [
  { label: 'Tổng quan', key: 'dashboard', icon: icon(GridOutline), path: '/' },
  { label: 'Sản phẩm', key: 'products', icon: icon(CubeOutline), path: '/products' },
  { label: 'Đơn hàng', key: 'orders', icon: icon(ReceiptOutline), path: '/orders' },
  { label: 'Đã bán', key: 'sold', icon: icon(CartOutline), path: '/sold' },
  { label: 'Cấu hình', key: 'settings', icon: icon(SettingsOutline), path: '/settings' },
]

const activeKey = computed(() => {
  const p = route.path
  if (p === '/' ) return 'dashboard'
  if (p.startsWith('/products')) return 'products'
  if (p.startsWith('/orders')) return 'orders'
  if (p.startsWith('/sold')) return 'sold'
  if (p.startsWith('/settings')) return 'settings'
  return ''
})

function onMenu(key, option) {
  router.push(option.path)
}

async function logout() {
  try { await api.logout() } catch {}
  authed.value = false
}

setUnauthorizedHandler(() => {
  authed.value = false
})

onMounted(async () => {
  try {
    await api.session()
    authed.value = true
  } catch {
    authed.value = false
  } finally {
    checking.value = false
  }
})

const collapsed = ref(false)
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="navyThemeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <div v-if="checking" style="height:100vh;display:grid;place-items:center">
          <n-spin size="large" />
        </div>

        <div v-else-if="!authed" style="height:100vh;display:grid;place-items:center;padding:24px">
          <n-result
            status="403"
            title="Cần đăng nhập"
            description="Mở bot Telegram và gửi /login để lấy liên kết đăng nhập quản trị."
          >
            <template #icon>
              <n-icon size="64" :component="RocketOutline" />
            </template>
          </n-result>
        </div>

        <n-layout v-else has-sider style="height:100vh">
          <n-layout-sider
            class="app-sider"
            bordered
            collapse-mode="width"
            :collapsed-width="64"
            :width="240"
            :collapsed="collapsed"
            show-trigger
            @collapse="collapsed = true"
            @expand="collapsed = false"
          >
            <div class="brand">
              <span class="brand-mark"><n-icon size="22" :component="CartOutline" /></span>
              <div v-if="!collapsed">
                <div class="brand-text">NCP Admin</div>
                <div class="brand-sub">Navy Control</div>
              </div>
            </div>
            <n-menu
              :value="activeKey"
              :options="menuOptions"
              :collapsed="collapsed"
              :collapsed-width="64"
              @update:value="onMenu"
            />
            <div style="position:absolute;bottom:16px;left:0;right:0;padding:0 16px">
              <n-button quaternary block @click="logout">
                <template #icon><n-icon :component="LogOutOutline" /></template>
                <span v-if="!collapsed">Đăng xuất</span>
              </n-button>
            </div>
          </n-layout-sider>

          <n-layout content-style="padding:28px 32px;overflow:auto">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </n-layout>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
