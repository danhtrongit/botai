// Wrapper fetch cho admin API: gửi kèm cookie, parse JSON, bắt 401.
const BASE = '/admin/api'

let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

async function request(method, path, body) {
  const opts = {
    method,
    credentials: 'include',
    headers: {},
  }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(`${BASE}${path}`, opts)
  if (resp.status === 401) {
    if (onUnauthorized) onUnauthorized()
    throw new Error('unauthorized')
  }
  let data = null
  const text = await resp.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }
  if (!resp.ok) {
    const msg = (data && data.detail) || `Lỗi ${resp.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

export const api = {
  session: () => request('GET', '/session'),
  logout: () => request('GET', '/logout'),
  overview: () => request('GET', '/overview'),

  products: () => request('GET', '/products'),
  createProduct: (p) => request('POST', '/products', p),
  updateProduct: (id, p) => request('PATCH', `/products/${id}`, p),
  toggleProduct: (id) => request('POST', `/products/${id}/toggle`),
  deleteProduct: (id) => request('DELETE', `/products/${id}`),

  productStock: (id) => request('GET', `/products/${id}/stock`),
  addStock: (p) => request('POST', '/stock', p),
  editStock: (id, p) => request('PATCH', `/stock/${id}`, p),
  deleteStock: (id) => request('DELETE', `/stock/${id}`),

  orders: (status) => request('GET', `/orders${status ? `?status=${status}` : ''}`),
  orderDetail: (id) => request('GET', `/orders/${id}`),
  completeUpgrade: (id, cost) => request('POST', `/orders/${id}/complete-upgrade`, { cost }),

  sold: () => request('GET', '/sold'),

  users: () => request('GET', '/users'),
  userDetail: (tgId) => request('GET', `/users/${tgId}`),
  adjustUser: (tgId, amount, note) => request('POST', `/users/${tgId}/adjust`, { amount, note }),
}

// Tiện ích định dạng tiền VND.
export function fmtVnd(amount) {
  return `${Number(amount || 0).toLocaleString('vi-VN')}đ`
}

export function fmtDt(dt) {
  return dt ? String(dt).slice(0, 19).replace('T', ' ') : '—'
}
