<script setup>
import { ref, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem,
  NInput, NInputNumber, NSelect, NPopconfirm, NIcon, NSpin, useMessage, NStatistic, NGrid, NGi, NH1, NText,
} from 'naive-ui'
import { AddOutline, CreateOutline, TrashOutline, ArrowBackOutline } from '@vicons/ionicons5'
import { api, fmtVnd } from '../api'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const productId = Number(route.params.id)

const loading = ref(true)
const product = ref(null)
const items = ref([])

const STATUS_OPTIONS = [
  { label: 'Còn', value: 'available' },
  { label: 'Đang giữ', value: 'reserved' },
  { label: 'Đã bán', value: 'sold' },
]

// ----- Modal sửa -----
const showEdit = ref(false)
const saving = ref(false)
const editForm = ref({ id: null, payload: '', cost: 0, status: 'available' })

function openEdit(row) {
  editForm.value = { id: row.id, payload: row.payload, cost: row.cost, status: row.status }
  showEdit.value = true
}

async function saveEdit() {
  saving.value = true
  try {
    await api.editStock(editForm.value.id, {
      payload: editForm.value.payload,
      cost: editForm.value.cost,
      status: editForm.value.status,
    })
    message.success('Đã cập nhật')
    showEdit.value = false
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await api.deleteStock(row.id)
    message.success('Đã xoá tài khoản')
    await load()
  } catch (e) {
    message.error(e.message)
  }
}

// ----- Modal nạp lô -----
const showAdd = ref(false)
const adding = ref(false)
const addForm = ref({ cost: 0, items: '' })

async function addStock() {
  if (!addForm.value.items.trim()) {
    message.warning('Chưa nhập tài khoản nào')
    return
  }
  adding.value = true
  try {
    const res = await api.addStock({
      product_id: productId,
      cost: addForm.value.cost,
      items: addForm.value.items,
    })
    message.success(`Đã nạp ${res.added} tài khoản`)
    showAdd.value = false
    addForm.value = { cost: 0, items: '' }
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    adding.value = false
  }
}

const STATUS_TAG = {
  available: { label: 'Còn', type: 'success' },
  reserved: { label: 'Đang giữ', type: 'warning' },
  sold: { label: 'Đã bán', type: 'default' },
}

const columns = [
  { title: 'ID', key: 'id', width: 64, render: (r) => h(NText, { depth: 3 }, { default: () => '#' + r.id }) },
  { title: 'Tài khoản', key: 'payload', render: (r) => h('span', { class: 'mono' }, r.payload) },
  { title: 'Giá vốn', key: 'cost', render: (r) => fmtVnd(r.cost) },
  {
    title: 'Trạng thái', key: 'status', width: 110,
    render: (r) => {
      const s = STATUS_TAG[r.status] || { label: r.status, type: 'default' }
      return h(NTag, { type: s.type, round: true, size: 'small', bordered: false }, { default: () => s.label })
    },
  },
  {
    title: 'Đơn', key: 'order_id', width: 80,
    render: (r) =>
      r.order_id
        ? h(NButton, { text: true, type: 'primary', class: 'mono', onClick: () => router.push(`/orders/${r.order_id}`) }, { default: () => '#' + r.order_id })
        : h(NText, { depth: 3 }, { default: () => '—' }),
  },
  {
    title: '', key: 'actions', width: 110,
    render: (r) =>
      h(NSpace, { size: 6 }, {
        default: () => [
          h(NButton, { size: 'small', secondary: true, onClick: () => openEdit(r) },
            { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }) }),
          h(NPopconfirm, { onPositiveClick: () => remove(r) }, {
            trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) }),
            default: () => `Xoá tài khoản #${r.id}?`,
          }),
        ],
      }),
  },
]

async function load() {
  loading.value = true
  try {
    const res = await api.productStock(productId)
    product.value = res.product
    items.value = res.items
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <n-button text style="margin-bottom:10px" @click="router.push('/products')">
      <template #icon><n-icon :component="ArrowBackOutline" /></template>
      Sản phẩm
    </n-button>

    <n-spin :show="loading">
      <template v-if="product">
        <n-space justify="space-between" align="center" style="margin-bottom:8px">
          <n-h1 style="margin:0">Kho — {{ product.name }}</n-h1>
          <n-button type="primary" @click="showAdd = true">
            <template #icon><n-icon :component="AddOutline" /></template>
            Nạp tài khoản
          </n-button>
        </n-space>

        <n-grid :cols="3" :x-gap="16" style="margin-bottom:20px">
          <n-gi><n-card :bordered="true"><n-statistic label="Còn" :value="product.stock.available" /></n-card></n-gi>
          <n-gi><n-card :bordered="true"><n-statistic label="Đang giữ" :value="product.stock.reserved" /></n-card></n-gi>
          <n-gi><n-card :bordered="true"><n-statistic label="Đã bán" :value="product.stock.sold" /></n-card></n-gi>
        </n-grid>

        <n-card :bordered="true">
          <n-data-table :columns="columns" :data="items" :bordered="false" :max-height="520" />
          <n-text depth="3" tag="p" style="font-size:0.82rem;margin:10px 0 0">
            Tối đa 500 mục mới nhất · đổi trạng thái về "Còn" sẽ gỡ gắn đơn.
          </n-text>
        </n-card>
      </template>
    </n-spin>

    <!-- Modal sửa -->
    <n-modal v-model:show="showEdit" preset="card" title="Sửa tài khoản" style="max-width:480px" :bordered="true">
      <n-form>
        <n-form-item label="Tài khoản (payload)">
          <n-input v-model:value="editForm.payload" />
        </n-form-item>
        <n-form-item label="Giá vốn (VND)">
          <n-input-number v-model:value="editForm.cost" :min="0" :step="1000" style="width:100%" />
        </n-form-item>
        <n-form-item label="Trạng thái">
          <n-select v-model:value="editForm.status" :options="STATUS_OPTIONS" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showEdit = false">Huỷ</n-button>
          <n-button type="primary" :loading="saving" @click="saveEdit">Lưu</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Modal nạp lô -->
    <n-modal v-model:show="showAdd" preset="card" title="Nạp tài khoản vào kho" style="max-width:520px" :bordered="true">
      <n-form>
        <n-form-item label="Giá vốn mỗi TK (VND) — cả lô dùng chung">
          <n-input-number v-model:value="addForm.cost" :min="0" :step="1000" style="width:100%" />
        </n-form-item>
        <n-form-item label="Mỗi dòng 1 tài khoản">
          <n-input
            v-model:value="addForm.items"
            type="textarea"
            :rows="7"
            placeholder="user1@mail.com|matkhau1&#10;user2@mail.com|matkhau2"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showAdd = false">Huỷ</n-button>
          <n-button type="primary" :loading="adding" @click="addStock">Nạp kho</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
