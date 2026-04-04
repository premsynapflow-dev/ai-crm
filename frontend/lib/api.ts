import axios from 'axios'

export const ACCESS_TOKEN_STORAGE_KEY = 'access_token'

const AUTH_REDIRECT_EXEMPT_PATHS = new Set(['/', '/login', '/signup', '/admin/login'])

function normalizePathname(pathname: string): string {
  if (!pathname || pathname === '/') {
    return '/'
  }

  return pathname.endsWith('/') ? pathname.slice(0, -1) : pathname
}

function getStoredAccessToken(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
}

function clearStoredAccessToken() {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
}

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const token = getStoredAccessToken()

  console.log('[auth] Authorization header before API call:', token)

  if (token) {
    const authorizationHeader = `Bearer ${token}`
    if (typeof config.headers?.set === 'function') {
      config.headers.set('Authorization', authorizationHeader)
    } else if (config.headers) {
      ;(config.headers as Record<string, string>).Authorization = authorizationHeader
    }
  } else if (typeof config.headers?.delete === 'function') {
    config.headers.delete('Authorization')
  } else if (config.headers) {
    delete (config.headers as Record<string, string>).Authorization
  }

  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      console.warn('Unauthorized - clearing token')
      clearStoredAccessToken()

      if (!AUTH_REDIRECT_EXEMPT_PATHS.has(normalizePathname(window.location.pathname))) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
