<script setup>
import { ref, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NCard, NSpin, NButton, NIcon, NSpace, NDescriptions, NDescriptionsItem,
  NDataTable, NForm, NFormItem, NInputNumber, useMessage, NTag, NH1, NText,
} from 'naive-ui'
import { ArrowBackOutline, SaveOutline } from '@vicons/ionicons5'
import { api, fmtVnd, fmtDt } from '../api'
import { statusTag } from '../status'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const orderId = Number(route.params.id)

const loading = ref(true)
const data = ref(null)
const cost = ref(0)
const saving = ref(false)

const itemColumns = [
  { title: 'ID', key: 'id', width: 64, render: (r) => h(NText, { depth: 3 }, { default: () => '#' + r.id }) },
  { title: 'Tài khoản', key: 'payload', render: (r) => h('span', { class: 'mono' }, r.payload) },
  { title: 'Giá vốn', key: 'cost', render: (r) => fmtVnd(r.cost) },
  { title: 'Trạng thái', key: 'status' },
]

async function load() {
  loading.value = true
  try {
    data.value = await api.orderDetail(orderId)
    cost.value = data.value.order.cost || 0
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function complete() {
  saving.value = true
  try {
    await api.completeUpgrade(orderId, cost.value)
    message.success('Đã lưu')
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <n-button text style="margin-bottom:10px" @click="router.push('/orders')">
      <template #icon><n-icon :component="ArrowBackOutline" /></template>
      Danh sách đơn
    </n-button>

    <n-spin :show="loading">
      <template v-if="data">
        <n-space align="center" style="margin-bottom:18px">
          <n-h1 style="margin:0">Đơn <span class="mono">{{ data.order.code }}</span></n-h1>
          <component :is="statusTag(data.order.status)" />
        </n-space>

        <n-card :bordered="true" style="margin-bottom:20px">
          <n-descriptions :column="2" label-placement="left">
            <n-descriptions-item label="Sản phẩm">
              {{ data.order.product_name || '#' + data.order.product_id }}
            </n-descriptions-item>
            <n-descriptions-item label="Khách">
              {{ data.order.buyer_username ? '@' + data.order.buyer_username : data.order.buyer_tg_id }}
              (id {{ data.order.buyer_tg_id }})
            </n-descriptions-item>
            <n-descriptions-item v-if="data.is_upgrade" label="Email nâng cấp">
              <span class="mono">{{ data.order.buyer_email || '—' }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="Số lượng">{{ data.order.quantity }}</n-descriptions-item>
            <n-descriptions-item label="Tổng tiền">{{ fmtVnd(data.order.total_amount) }}</n-descriptions-item>
            <n-descriptions-item label="Giá vốn">{{ fmtVnd(data.cost) }}</n-descriptions-item>
            <n-descriptions-item label="Lợi nhuận">
              <n-text :type="data.profit >= 0 ? 'success' : 'error'" strong>
                {{ fmtVnd(data.profit) }}
              </n-text>
            </n-descriptions-item>
            <n-descriptions-item label="Mã giao dịch">
              <span class="mono">{{ data.order.payment_tx_id || '—' }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="Thời gian" :span="2">
              <n-text depth="3" style="font-size:0.84rem">
                Tạo: {{ fmtDt(data.order.created_at) }} · TT: {{ fmtDt(data.order.paid_at) }} · Hết hạn: {{ fmtDt(data.order.expires_at) }}
              </n-text>
            </n-descriptions-item>
          </n-descriptions>
        </n-card>

        <!-- Đơn nâng cấp chính chủ -->
        <n-card v-if="data.is_upgrade" title="Nâng cấp chính chủ" :bordered="true">
          <n-text tag="p" depth="2" style="margin:0 0 14px">
            Email khách: <span class="mono">{{ data.order.buyer_email || '—' }}</span>.
            {{ data.order.status === 'awaiting_upgrade'
              ? 'Nhập giá vốn rồi bấm hoàn tất để chuyển đơn sang đã giao.'
              : 'Cập nhật giá vốn của đơn (dùng để tính lợi nhuận).' }}
          </n-text>
          <n-form>
            <n-form-item label="Giá vốn (VND)">
              <n-input-number v-model:value="cost" :min="0" :step="1000" style="max-width:280px" />
            </n-form-item>
          </n-form>
          <n-button type="primary" :loading="saving" @click="complete">
            <template #icon><n-icon :component="SaveOutline" /></template>
            {{ data.order.status === 'awaiting_upgrade' ? 'Hoàn tất nâng cấp' : 'Lưu giá vốn' }}
          </n-button>
        </n-card>

        <!-- Đơn tài khoản -->
        <n-card v-else title="Tài khoản trong đơn" :bordered="true">
          <n-data-table :columns="itemColumns" :data="data.items" :bordered="false" />
        </n-card>
      </template>
    </n-spin>
  </div>
</template>
