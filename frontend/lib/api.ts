import axios from 'axios'

const AUTH_REDIRECT_EXEMPT_PATHS = new Set(['/', '/login', '/signup', '/admin/login'])

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
      !AUTH_REDIRECT_EXEMPT_PATHS.has(window.location.pathname)
    ) {
      window.location.href = '/'
    }
    return Promise.reject(error)
  }
)

export default api
