<script setup>
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  NGrid, NGi, NCard, NDataTable, NTag, NSpin, NSpace, NIcon, NAlert, NText,
} from 'naive-ui'
import { CheckmarkCircleOutline, AlertCircleOutline } from '@vicons/ionicons5'
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
    <h1 class="page-title">Tổng quan</h1>
    <p class="page-sub">Doanh thu, lợi nhuận và tình trạng hệ thống.</p>

    <n-spin :show="loading">
      <template v-if="data">
        <div class="stat-grid" style="margin-bottom:22px">
          <n-card class="stat-card" :bordered="true">
            <div class="stat-label">Doanh thu</div>
            <div class="stat-num">{{ fmtVnd(data.stats.revenue) }}</div>
          </n-card>
          <n-card class="stat-card" :bordered="true">
            <div class="stat-label">Giá vốn</div>
            <div class="stat-num" style="color:#aebbd6">{{ fmtVnd(data.stats.cost) }}</div>
          </n-card>
          <n-card class="stat-card" :bordered="true">
            <div class="stat-label">Lợi nhuận</div>
            <div class="stat-num" style="color:#22c55e">{{ fmtVnd(data.stats.profit) }}</div>
          </n-card>
          <n-card class="stat-card" :bordered="true">
            <div class="stat-label">Đơn đã giao</div>
            <div class="stat-num">{{ data.stats.delivered }}</div>
          </n-card>
        </div>

        <n-alert
          v-if="data.mbbank.configured"
          type="success" :bordered="true" style="margin-bottom:22px"
          title="MBBank đã kết nối"
        >
          Đang quét giao dịch tự động · user
          <span class="mono">{{ data.mbbank.username_masked }}</span>
          · TK <span class="mono">{{ data.mbbank.account_no || 'tự dò' }}</span>
        </n-alert>
        <n-alert
          v-else type="warning" :bordered="true" style="margin-bottom:22px"
          title="Chưa cấu hình MBBank"
        >
          Bot chưa thể tự đối soát. Vào <b>Cấu hình</b> để nhập TK/MK MBBank.
        </n-alert>

        <n-card title="Đơn gần đây" :bordered="true">
          <n-data-table
            :columns="orderColumns"
            :data="data.recent_orders"
            :row-props="rowProps"
            :bordered="false"
          />
        </n-card>
      </template>
    </n-spin>
  </div>
</template>
