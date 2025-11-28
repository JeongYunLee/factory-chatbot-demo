
const apiBase = (process.env.VITE_API_URL || '/projects/data-chatbot/api/').replace(/\/?$/, '/')

export default defineNuxtConfig({
  devtools: { enabled: true },
  
  app: {
    baseURL: '/projects/data-chatbot/',
  },
  runtimeConfig: {
    public: {
      apiUrl: apiBase
    }
  }
});
