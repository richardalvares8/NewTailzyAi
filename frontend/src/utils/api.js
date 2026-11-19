import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('tailzyai_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Turn an axios error into a message a user (and we, when debugging) can act on.
export const errorMessage = (error, fallback = 'Something went wrong') => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (!error?.response) {
    return BACKEND_URL
      ? "Can't reach the Tailzyai server. Check your internet connection and try again."
      : 'App is not configured with a server address.';
  }
  return `${fallback} (server error ${error.response.status})`;
};

export default api;