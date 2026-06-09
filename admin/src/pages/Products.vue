<script setup>
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem,
  NInput, NInputNumber, NSelect, NSwitch, NPopconfirm, NIcon, useMessage, NH1, NText,
} from 'naive-ui'
import {
  AddOutline, CreateOutline, TrashOutline, CubeOutline, EyeOutline, EyeOffOutline,
} from '@vicons/ionicons5'
import { api, fmtVnd } from '../api'

const router = useRouter()
const message = useMessage()

const loading = ref(true)
const products = ref([])

const KIND_OPTIONS = [
  { label: 'Tài khoản (giao từ kho)', value: 'account' },
  { label: 'Nâng cấp chính chủ', value: 'upgrade' },
]

// ----- Modal thêm/sửa -----
const showModal = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({ name: '', price: 0, description: '', kind: 'account', is_active: true })

function openCreate() {
  editingId.value = null
  form.value = { name: '', price: 0, description: '', kind: 'account', is_active: true }
  showModal.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    name: row.name,
    price: row.price,
    description: row.description || '',
    kind: row.kind,
    is_active: row.is_active,
  }
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    message.warning('Vui lòng nhập tên sản phẩm')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await api.updateProduct(editingId.value, form.value)
      message.success('Đã cập nhật sản phẩm')
    } else {
      await api.createProduct(form.value)
      message.success('Đã thêm sản phẩm')
    }
    showModal.value = false
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  try {
    await api.toggleProduct(row.id)
    await load()
  } catch (e) {
    message.error(e.message)
  }
}

async function remove(row) {
  try {
    await api.deleteProduct(row.id)
    message.success('Đã xoá sản phẩm')
    await load()
  } catch (e) {
    message.error(e.message)
  }
}

const columns = [
  { title: 'ID', key: 'id', width: 64, render: (r) => h(NText, { depth: 3 }, { default: () => '#' + r.id }) },
  {
    title: 'Tên', key: 'name',
    render: (r) =>
      h(NSpace, { size: 8, align: 'center' }, {
        default: () => [
          h('span', { style: 'font-weight:500' }, r.name),
          h(NTag, { size: 'small', round: true, bordered: false, type: r.kind === 'upgrade' ? 'primary' : 'default' },
            { default: () => r.kind_label }),
        ],
      }),
  },
  { title: 'Giá', key: 'price', render: (r) => fmtVnd(r.price) },
  {
    title: 'Sẵn / Giữ / Bán', key: 'stock',
    render: (r) =>
      r.kind === 'upgrade'
        ? h(NText, { depth: 3 }, { default: () => '—' })
        : `${r.stock.available} / ${r.stock.reserved} / ${r.stock.sold}`,
  },
  {
    title: 'Trạng thái', key: 'is_active',
    render: (r) =>
      h(NTag, { type: r.is_active ? 'success' : 'default', round: true, size: 'small', bordered: false },
        { default: () => (r.is_active ? 'Đang bán' : 'Đã ẩn') }),
  },
  {
    title: 'Thao tác', key: 'actions', width: 280,
    render: (r) =>
      h(NSpace, { size: 6 }, {
        default: () => [
          r.kind !== 'upgrade'
            ? h(NButton, {
                size: 'small', secondary: true,
                onClick: () => router.push(`/products/${r.id}/stock`),
              }, { icon: () => h(NIcon, null, { default: () => h(CubeOutline) }), default: () => 'Kho' })
            : null,
          h(NButton, {
            size: 'small', secondary: true,
            onClick: () => openEdit(r),
          }, { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }), default: () => 'Sửa' }),
          h(NButton, {
            size: 'small', secondary: true,
            onClick: () => toggle(r),
          }, { icon: () => h(NIcon, null, { default: () => h(r.is_active ? EyeOffOutline : EyeOutline) }) }),
          h(NPopconfirm, { onPositiveClick: () => remove(r) }, {
            trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) }),
            default: () => `Xoá sản phẩm #${r.id}? (Sản phẩm đã có đơn sẽ không xoá được)`,
          }),
        ],
      }),
  },
]

async function load() {
  loading.value = true
  try {
    const res = await api.products()
    products.value = res.products
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <n-space justify="space-between" align="center" style="margin-bottom:8px">
      <n-h1 style="margin:0">Sản phẩm</n-h1>
      <n-button type="primary" @click="openCreate">
        <template #icon><n-icon :component="AddOutline" /></template>
        Thêm sản phẩm
      </n-button>
    </n-space>
    <n-text depth="3">Quản lý sản phẩm, kho và trạng thái bán.</n-text>

    <n-card :bordered="true">
      <n-data-table
        :columns="columns"
        :data="products"
        :loading="loading"
        :bordered="false"
      />
    </n-card>

    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editingId ? `Sửa sản phẩm #${editingId}` : 'Thêm sản phẩm'"
      style="max-width:520px"
      :bordered="true"
    >
      <n-form>
        <n-form-item label="Tên sản phẩm">
          <n-input v-model:value="form.name" placeholder="VD: Netflix Premium 1 tháng" />
        </n-form-item>
        <n-form-item label="Loại sản phẩm">
          <n-select v-model:value="form.kind" :options="KIND_OPTIONS" />
        </n-form-item>
        <n-form-item label="Giá (VND)">
          <n-input-number v-model:value="form.price" :min="0" :step="1000" style="width:100%" />
        </n-form-item>
        <n-form-item label="Mô tả">
          <n-input v-model:value="form.description" type="textarea" :rows="2" />
        </n-form-item>
        <n-form-item v-if="editingId" label="Đang bán">
          <n-switch v-model:value="form.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">Huỷ</n-button>
          <n-button type="primary" :loading="saving" @click="save">Lưu</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
