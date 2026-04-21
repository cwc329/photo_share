import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL
if (!baseURL) {
  throw new Error('VITE_API_BASE_URL is required')
}

const api = axios.create({ baseURL, withCredentials: true })

export default api
