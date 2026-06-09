<script setup>
import { ref, onMounted, h, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NDataTable, NSpace, NButton, NIcon } from 'naive-ui'
import { api, fmtVnd, fmtDt } from '../api'
import { statusTag, ORDER_STATUS_FILTERS } from '../status'

const router = useRouter()
const loading = ref(true)
const orders = ref([])
const filter = ref('')

const columns = [
  { title: 'Mã', key: 'code', render: (r) => h('span', { class: 'mono' }, r.code) },
  { title: 'Sản phẩm', key: 'product_name', render: (r) => r.product_name || `#${r.product_id}` },
  {
    title: 'Khách', key: 'buyer',
    render: (r) => (r.buyer_username ? '@' + r.buyer_username : r.buyer_tg_id),
  },
  { title: 'SL', key: 'quantity', width: 60 },
  { title: 'Tiền', key: 'total_amount', render: (r) => fmtVnd(r.total_amount) },
  { title: 'Trạng thái', key: 'status', render: (r) => statusTag(r.status) },
  { title: 'Tạo lúc', key: 'created_at', render: (r) => h('span', { style: 'color:#6b7a99;font-size:0.84rem' }, fmtDt(r.created_at)) },
]

function rowProps(row) {
  return { style: 'cursor:pointer', onClick: () => router.push(`/orders/${row.id}`) }
}

async function load() {
  loading.value = true
  try {
    const res = await api.orders(filter.value)
    orders.value = res.orders
  } finally {
    loading.value = false
  }
}

watch(filter, load)
onMounted(load)
</script>

<template>
  <div>
    <h1 class="page-title">Lịch sử đơn hàng</h1>
    <p class="page-sub">Tối đa 200 đơn mới nhất.</p>

    <n-space style="margin-bottom:16px">
      <n-button
        v-for="f in ORDER_STATUS_FILTERS"
        :key="f.value"
        size="small"
        :type="filter === f.value ? 'primary' : 'default'"
        :secondary="filter !== f.value"
        @click="filter = f.value"
      >
        {{ f.label }}
      </n-button>
    </n-space>

    <n-card :bordered="true">
      <n-data-table
        :columns="columns"
        :data="orders"
        :loading="loading"
        :row-props="rowProps"
        :bordered="false"
      />
    </n-card>
  </div>
</template>
