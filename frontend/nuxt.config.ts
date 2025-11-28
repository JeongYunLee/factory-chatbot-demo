// https://nuxt.com/docs/api/configuration/nuxt-config
const apiBase =
  (globalThis as Record<string, any>)?.process?.env?.NUXT_PUBLIC_API_BASE ??
  'http://127.0.0.1:8000'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  runtimeConfig: {
    public: {
      apiBase
    }
  }
})
