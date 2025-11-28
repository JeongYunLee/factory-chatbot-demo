export default defineNuxtConfig({
  devtools: { enabled: true },

  app: {
    baseURL: '/projects/data-chatbot/',
  },

  runtimeConfig: {
    public: {
      // 브라우저에서도 접근 가능한 API URL
      apiUrl: process.env.VITE_API_URL?.replace(/\/?$/, '/') || 'http://localhost:8000/api/'
    }
  }
})