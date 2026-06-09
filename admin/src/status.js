import { h } from 'vue'
import { NTag } from 'naive-ui'

// Nhãn + màu cho trạng thái đơn (đồng bộ với bot/db/models.py).
const STATUS = {
  pending: { label: 'Chờ TT', type: 'warning' },
  paid: { label: 'Đã trả', type: 'info' },
  awaiting_upgrade: { label: 'Chờ nâng cấp', type: 'primary' },
  delivered: { label: 'Đã giao', type: 'success' },
  expired: { label: 'Hết hạn', type: 'default' },
  failed: { label: 'Lỗi', type: 'error' },
}

export function statusLabel(status) {
  return (STATUS[status] || { label: status }).label
}

export function statusTag(status) {
  const s = STATUS[status] || { label: status, type: 'default' }
  return h(NTag, { type: s.type, round: true, size: 'small', bordered: false }, { default: () => s.label })
}

export const ORDER_STATUS_FILTERS = [
  { label: 'Tất cả', value: '' },
  { label: 'Chờ TT', value: 'pending' },
  { label: 'Chờ nâng cấp', value: 'awaiting_upgrade' },
  { label: 'Đã giao', value: 'delivered' },
  { label: 'Hết hạn', value: 'expired' },
  { label: 'Lỗi', value: 'failed' },
]
