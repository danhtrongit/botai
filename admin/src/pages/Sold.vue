<script setup>
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NDataTable } from 'naive-ui'
import { api, fmtVnd, fmtDt } from '../api'

const router = useRouter()
const loading = ref(true)
const sold = ref([])

const columns = [
  { title: 'Sản phẩm', key: 'product_name', render: (r) => h('span', { style: 'font-weight:500' }, r.product_name) },
  { title: 'Tài khoản đã giao', key: 'payload', render: (r) => h('span', { class: 'mono' }, r.payload) },
  {
    title: 'Đơn', key: 'order_code',
    render: (r) => h('a', {
      class: 'mono', style: 'color:#60a5fa;cursor:pointer',
      onClick: () => router.push(`/orders/${r.order_id}`),
    }, r.order_code),
  },
  { title: 'Giá bán', key: 'unit_sale', render: (r) => fmtVnd(r.unit_sale) },
  { title: 'Giá vốn', key: 'cost', render: (r) => h('span', { style: 'color:#aebbd6' }, fmtVnd(r.cost)) },
  {
    title: 'Lợi nhuận', key: 'profit',
    render: (r) => h('span', { style: { color: r.profit >= 0 ? '#22c55e' : '#f43f5e', fontWeight: 600 } }, fmtVnd(r.profit)),
  },
  { title: 'Bán lúc', key: 'paid_at', render: (r) => h('span', { style: 'color:#6b7a99;font-size:0.84rem' }, fmtDt(r.paid_at)) },
]

onMounted(async () => {
  try {
    const res = await api.sold()
    sold.value = res.sold
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="page-title">Tài khoản đã bán</h1>
    <p class="page-sub">Tối đa 300 mục mới nhất · Giá bán = tiền đơn ÷ số lượng.</p>

    <n-card :bordered="true">
      <n-data-table :columns="columns" :data="sold" :loading="loading" :bordered="false" :max-height="600" />
    </n-card>
  </div>
</template>
