<script setup>
import { ref, onMounted } from 'vue'
import {
  NCard, NForm, NFormItem, NInput, NButton, NIcon, NSpace, NAlert, useMessage, NSpin, NH1, NText,
} from 'naive-ui'
import { ShieldCheckmarkOutline } from '@vicons/ionicons5'
import { api } from '../api'

const message = useMessage()
const loading = ref(true)
const saving = ref(false)
const status = ref({ configured: false })
const form = ref({ username: '', password: '', account_no: '' })

async function load() {
  loading.value = true
  try {
    status.value = await api.mbbank()
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.value.username.trim() || !form.value.password) {
    message.warning('Vui lòng nhập tên đăng nhập và mật khẩu')
    return
  }
  saving.value = true
  try {
    await api.saveMbbank(form.value)
    message.success('Đã lưu & bật quét giao dịch')
    form.value.password = ''
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
    <n-h1 style="margin-top:0">Cấu hình</n-h1>
    <n-text depth="3">Kết nối MBBank để tự đối soát thanh toán.</n-text>

    <n-spin :show="loading">
      <n-alert
        v-if="status.configured"
        type="success" :bordered="true" style="margin-bottom:18px"
        title="MBBank đã cấu hình"
      >
        user <span class="mono">{{ status.username_masked }}</span> ·
        TK <span class="mono">{{ status.account_no || 'tự dò' }}</span>
      </n-alert>
      <n-alert
        v-else type="warning" :bordered="true" style="margin-bottom:18px"
        title="Chưa cấu hình MBBank"
      >
        Bot chưa thể tự quét giao dịch & giao hàng.
      </n-alert>

      <n-card title="Kết nối MBBank" :bordered="true" style="max-width:560px">
        <n-text depth="3" tag="p" style="margin:0 0 16px;font-size:0.86rem">
          TK/MK gửi qua HTTPS và được mã hoá (Fernet) trước khi lưu. Bỏ trống Số TK để tự dò.
        </n-text>
        <n-form>
          <n-form-item label="Tên đăng nhập MBBank">
            <n-input v-model:value="form.username" placeholder="Tên đăng nhập" />
          </n-form-item>
          <n-form-item label="Mật khẩu MBBank">
            <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="Mật khẩu" />
          </n-form-item>
          <n-form-item label="Số tài khoản (tuỳ chọn)">
            <n-input v-model:value="form.account_no" placeholder="Để trống để tự dò" />
          </n-form-item>
        </n-form>
        <n-button type="primary" :loading="saving" @click="save">
          <template #icon><n-icon :component="ShieldCheckmarkOutline" /></template>
          Lưu & bật quét
        </n-button>
      </n-card>
    </n-spin>
  </div>
</template>
