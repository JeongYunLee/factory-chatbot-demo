export default defineNuxtConfig({
  devtools: { enabled: true },

  app: {
    baseURL: '/projects/data-chatbot/',
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      // 브라우저에서도 접근 가능한 API URL
      // 백엔드의 root_path="/projects/data-chatbot"와 일치하도록 설정
      apiUrl: (process.env as any).VITE_API_URL?.replace(/\/?$/, '/') || 'http://localhost:8000/projects/data-chatbot/api/'
    }
  }
})