<script setup>
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NDataTable, NButton, NH1, NText } from 'naive-ui'
import { api, fmtVnd, fmtDt } from '../api'

const router = useRouter()
const loading = ref(true)
const sold = ref([])

const columns = [
  { title: 'Sản phẩm', key: 'product_name', render: (r) => h('span', { style: 'font-weight:500' }, r.product_name) },
  { title: 'Tài khoản đã giao', key: 'payload', render: (r) => h('span', { class: 'mono' }, r.payload) },
  {
    title: 'Đơn', key: 'order_code',
    render: (r) => h(NButton, {
      text: true, type: 'primary', class: 'mono',
      onClick: () => router.push(`/orders/${r.order_id}`),
    }, { default: () => r.order_code }),
  },
  { title: 'Giá bán', key: 'unit_sale', render: (r) => fmtVnd(r.unit_sale) },
  { title: 'Giá vốn', key: 'cost', render: (r) => h(NText, { depth: 3 }, { default: () => fmtVnd(r.cost) }) },
  {
    title: 'Lợi nhuận', key: 'profit',
    render: (r) => h(NText, { type: r.profit >= 0 ? 'success' : 'error', strong: true }, { default: () => fmtVnd(r.profit) }),
  },
  { title: 'Bán lúc', key: 'paid_at', render: (r) => h(NText, { depth: 3, style: 'font-size:0.84rem' }, { default: () => fmtDt(r.paid_at) }) },
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
    <n-h1 style="margin-top:0">Tài khoản đã bán</n-h1>
    <n-text depth="3">Tối đa 300 mục mới nhất · Giá bán = tiền đơn ÷ số lượng.</n-text>

    <n-card :bordered="true">
      <n-data-table :columns="columns" :data="sold" :loading="loading" :bordered="false" :max-height="600" />
    </n-card>
  </div>
</template>
