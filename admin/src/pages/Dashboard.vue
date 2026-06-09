<script setup>
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  NGrid, NGi, NCard, NStatistic, NDataTable, NSpin, NAlert, NH1, NText,
} from 'naive-ui'
import { api, fmtVnd } from '../api'
import { statusTag } from '../status'

const router = useRouter()
const loading = ref(true)
const data = ref(null)

const orderColumns = [
  { title: 'Mã', key: 'code', render: (r) => h('span', { class: 'mono' }, r.code) },
  {
    title: 'Khách', key: 'buyer',
    render: (r) => (r.buyer_username ? '@' + r.buyer_username : r.buyer_tg_id),
  },
  { title: 'SL', key: 'quantity' },
  { title: 'Tiền', key: 'total_amount', render: (r) => fmtVnd(r.total_amount) },
  { title: 'Trạng thái', key: 'status', render: (r) => statusTag(r.status) },
]

function rowProps(row) {
  return {
    style: 'cursor:pointer',
    onClick: () => router.push(`/orders/${row.id}`),
  }
}

onMounted(async () => {
  try {
    data.value = await api.overview()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <n-h1 style="margin-top:0">Tổng quan</n-h1>
    <n-text depth="3">Doanh thu, lợi nhuận và tình trạng hệ thống.</n-text>

    <n-spin :show="loading">
      <template v-if="data">
        <n-grid cols="2 s:4" responsive="screen" :x-gap="16" :y-gap="16" style="margin:20px 0">
          <n-gi><n-card><n-statistic label="Doanh thu" :value="fmtVnd(data.stats.revenue)" /></n-card></n-gi>
          <n-gi><n-card><n-statistic label="Giá vốn" :value="fmtVnd(data.stats.cost)" /></n-card></n-gi>
          <n-gi><n-card><n-statistic label="Lợi nhuận" :value="fmtVnd(data.stats.profit)" /></n-card></n-gi>
          <n-gi><n-card><n-statistic label="Đơn đã giao" :value="data.stats.delivered" /></n-card></n-gi>
        </n-grid>

        <n-alert
          v-if="data.mbbank.configured"
          type="success" style="margin-bottom:20px" title="MBBank đã kết nối"
        >
          Đang quét giao dịch tự động · user
          <span class="mono">{{ data.mbbank.username_masked }}</span>
          · TK <span class="mono">{{ data.mbbank.account_no || 'tự dò' }}</span>
        </n-alert>
        <n-alert
          v-else type="warning" style="margin-bottom:20px" title="Chưa cấu hình MBBank"
        >
          Bot chưa thể tự đối soát. Vào <b>Cấu hình</b> để nhập TK/MK MBBank.
        </n-alert>

        <n-card title="Đơn gần đây">
          <n-data-table :columns="orderColumns" :data="data.recent_orders" :row-props="rowProps" />
        </n-card>
      </template>
    </n-spin>
  </div>
</template>
