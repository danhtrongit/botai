<script setup>
import { ref, onMounted, h } from 'vue'
import {
  NCard, NDataTable, NButton, NSpace, NModal, NForm, NFormItem,
  NInput, NInputNumber, NIcon, useMessage, NH1, NText, NTag, NRadioGroup, NRadioButton,
} from 'naive-ui'
import { api, fmtVnd, fmtDt } from '../api'

const message = useMessage()
const loading = ref(true)
const users = ref([])

// ----- Modal cộng/trừ tiền -----
const showAdjust = ref(false)
const saving = ref(false)
const adjustForm = ref({ tg_id: null, username: '', direction: 'credit', amount: 0, note: '' })

// ----- Modal lịch sử ví -----
const showHistory = ref(false)
const historyLoading = ref(false)
const historyUser = ref(null)
const historyTxs = ref([])

const TX_LABEL = {
  topup: 'Nạp tiền', admin_credit: 'Admin cộng', admin_debit: 'Admin trừ',
  purchase: 'Mua hàng', refund: 'Hoàn tiền',
}

const columns = [
  { title: 'TG ID', key: 'tg_id', render: (r) => h('span', { class: 'mono' }, r.tg_id) },
  { title: 'Username', key: 'username', render: (r) => (r.username ? '@' + r.username : '—') },
  {
    title: 'Số dư', key: 'balance',
    render: (r) => h(NText, { type: r.balance > 0 ? 'success' : undefined, strong: true }, { default: () => fmtVnd(r.balance) }),
  },
  { title: 'Cập nhật', key: 'updated_at', render: (r) => h(NText, { depth: 3, style: 'font-size:0.84rem' }, { default: () => fmtDt(r.updated_at) }) },
  {
    title: 'Thao tác', key: 'actions',
    render: (r) => h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', type: 'primary', secondary: true, onClick: () => openAdjust(r) }, { default: () => 'Cộng/Trừ' }),
        h(NButton, { size: 'small', onClick: () => openHistory(r) }, { default: () => 'Lịch sử' }),
      ],
    }),
  },
]

function openAdjust(row) {
  adjustForm.value = { tg_id: row.tg_id, username: row.username, direction: 'credit', amount: 0, note: '' }
  showAdjust.value = true
}

async function saveAdjust() {
  const amt = Number(adjustForm.value.amount || 0)
  if (amt <= 0) {
    message.warning('Nhập số tiền lớn hơn 0')
    return
  }
  const signed = adjustForm.value.direction === 'debit' ? -amt : amt
  saving.value = true
  try {
    const res = await api.adjustUser(adjustForm.value.tg_id, signed, adjustForm.value.note)
    message.success(`Đã cập nhật. Số dư mới: ${fmtVnd(res.balance)}`)
    showAdjust.value = false
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function openHistory(row) {
  historyUser.value = row
  showHistory.value = true
  historyLoading.value = true
  try {
    const res = await api.userDetail(row.tg_id)
    historyTxs.value = res.txs
  } catch (e) {
    message.error(e.message)
  } finally {
    historyLoading.value = false
  }
}

const historyColumns = [
  {
    title: 'Số tiền', key: 'amount',
    render: (r) => h(NText, { type: r.amount >= 0 ? 'success' : 'error', strong: true },
      { default: () => `${r.amount >= 0 ? '+' : ''}${fmtVnd(r.amount)}` }),
  },
  { title: 'Loại', key: 'type', render: (r) => TX_LABEL[r.type] || r.type },
  {
    title: 'Trạng thái', key: 'status',
    render: (r) => h(NTag, { size: 'small', type: r.status === 'confirmed' ? 'success' : (r.status === 'rejected' ? 'error' : 'warning') },
      { default: () => r.status }),
  },
  { title: 'Mã', key: 'ref_code', render: (r) => h('span', { class: 'mono' }, r.ref_code || '—') },
  { title: 'Ghi chú', key: 'note', render: (r) => r.note || '—' },
  { title: 'Lúc', key: 'created_at', render: (r) => h(NText, { depth: 3, style: 'font-size:0.84rem' }, { default: () => fmtDt(r.created_at) }) },
]

async function load() {
  loading.value = true
  try {
    const res = await api.users()
    users.value = res.users
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <n-h1 style="margin-top:0">Người dùng & Ví</n-h1>
    <n-text depth="3">Tối đa 300 người dùng mới nhất. Cộng/trừ số dư ví trực tiếp tại đây.</n-text>

    <n-card :bordered="true" style="margin-top:16px">
      <n-data-table :columns="columns" :data="users" :loading="loading" :bordered="false" />
    </n-card>

    <!-- Modal cộng/trừ -->
    <n-modal v-model:show="showAdjust" preset="card" style="max-width:440px" title="Điều chỉnh số dư ví">
      <n-form>
        <n-form-item label="Người dùng">
          <n-text class="mono">{{ adjustForm.username ? '@' + adjustForm.username : adjustForm.tg_id }}</n-text>
        </n-form-item>
        <n-form-item label="Hành động">
          <n-radio-group v-model:value="adjustForm.direction">
            <n-radio-button value="credit">➕ Cộng tiền</n-radio-button>
            <n-radio-button value="debit">➖ Trừ tiền</n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item label="Số tiền (VND)">
          <n-input-number v-model:value="adjustForm.amount" :min="0" :step="10000" style="width:100%" />
        </n-form-item>
        <n-form-item label="Ghi chú (tuỳ chọn)">
          <n-input v-model:value="adjustForm.note" placeholder="Lý do điều chỉnh..." />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showAdjust = false">Huỷ</n-button>
          <n-button type="primary" :loading="saving" @click="saveAdjust">Xác nhận</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Modal lịch sử -->
    <n-modal v-model:show="showHistory" preset="card" style="max-width:760px" title="Lịch sử giao dịch ví">
      <n-text v-if="historyUser" depth="3">
        {{ historyUser.username ? '@' + historyUser.username : historyUser.tg_id }} — Số dư: {{ fmtVnd(historyUser.balance) }}
      </n-text>
      <n-data-table
        style="margin-top:12px"
        :columns="historyColumns"
        :data="historyTxs"
        :loading="historyLoading"
        :bordered="false"
        :max-height="420"
      />
    </n-modal>
  </div>
</template>
