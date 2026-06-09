import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'
import Products from './pages/Products.vue'
import Stock from './pages/Stock.vue'
import Orders from './pages/Orders.vue'
import OrderDetail from './pages/OrderDetail.vue'
import Sold from './pages/Sold.vue'
import Users from './pages/Users.vue'

const routes = [
  { path: '/', name: 'dashboard', component: Dashboard, meta: { title: 'Tổng quan' } },
  { path: '/products', name: 'products', component: Products, meta: { title: 'Sản phẩm' } },
  { path: '/products/:id/stock', name: 'stock', component: Stock, meta: { title: 'Kho' } },
  { path: '/orders', name: 'orders', component: Orders, meta: { title: 'Đơn hàng' } },
  { path: '/orders/:id', name: 'order-detail', component: OrderDetail, meta: { title: 'Chi tiết đơn' } },
  { path: '/sold', name: 'sold', component: Sold, meta: { title: 'Đã bán' } },
  { path: '/users', name: 'users', component: Users, meta: { title: 'Người dùng' } },
]

export default createRouter({
  // base /admin/ khớp với Vite base + FastAPI mount.
  history: createWebHistory('/admin/'),
  routes,
})
