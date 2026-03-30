import axios from 'axios'

const AUTH_REDIRECT_EXEMPT_PATHS = new Set(['/', '/login', '/signup', '/admin/login'])

function normalizePathname(pathname: string): string {
  if (!pathname || pathname === '/') {
    return '/'
  }

  return pathname.endsWith('/') ? pathname.slice(0, -1) : pathname
}

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      typeof window !== 'undefined' &&
      !AUTH_REDIRECT_EXEMPT_PATHS.has(normalizePathname(window.location.pathname))
    ) {
      window.location.href = '/'
    }
    return Promise.reject(error)
  }
)

export default api
