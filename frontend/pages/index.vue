<template>
  <div class="page">
    <div class="chat-card">
      <ChatHeader
        :session-id="sessionId"
        :is-loading="isLoading"
        @reset="resetConversation"
      />

      <div class="messages-container" ref="messageContainer">
        <ChatMessageList :messages="messages" :is-loading="isLoading" />
      </div>

      <Transition name="fade">
        <p v-if="errorMessage" class="error-banner">
          {{ errorMessage }}
        </p>
      </Transition>

      <ChatInput
        ref="chatInputRef"
        :disabled="isLoading"
        @submit="sendMessage"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import ChatHeader from '~/components/ChatHeader.vue'
import ChatMessageList, {
  type ChatMessage
} from '~/components/ChatMessageList.vue'
import ChatInput from '~/components/ChatInput.vue'

interface ApiResponse {
  answer: string
  session_id: string
  status: string
  message_count?: number
  error_type?: string
}

const config = useRuntimeConfig()
const sessionId = useState<string | null>('factory-session', () => null)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

const createId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const buildWelcomeMessage = (): ChatMessage => ({
  id: createId(),
  role: 'bot',
  text: '안녕하세요! 서울 지역 공장 등록 데이터를 기반으로 질문을 도와드리는 챗봇입니다. 궁금한 점을 자연어로 물어보세요.',
  timestamp: Date.now()
})

const messages = ref<ChatMessage[]>([buildWelcomeMessage()])
const chatInputRef = ref<InstanceType<typeof ChatInput> | null>(null)

const messageContainer = ref<HTMLElement | null>(null)

watch(
  () => messages.value.length,
  () => {
    nextTick(() => {
      if (messageContainer.value) {
        messageContainer.value.scrollTop = messageContainer.value.scrollHeight
      }
    })
  }
)

const callBackend = async <T,>(
  endpoint: string,
  payload?: Record<string, unknown>
): Promise<T> => {
  return $fetch<T>(endpoint, {
    method: 'POST',
    baseURL: config.public.apiBase,
    body: payload ?? {}
  })
}

const sendMessage = async (content: string) => {
  if (!content.trim() || isLoading.value) return

  messages.value.push({
    id: createId(),
    role: 'user',
    text: content,
    timestamp: Date.now()
  })

  isLoading.value = true
  errorMessage.value = null

  try {
    const response = await callBackend<ApiResponse>('/api/', {
      message: content,
      session_id: sessionId.value ?? undefined
    })

    if (response?.session_id) {
      sessionId.value = response.session_id
    }

    messages.value.push({
      id: createId(),
      role: 'bot',
      text: response?.answer ?? '응답을 받을 수 없습니다.',
      timestamp: Date.now()
    })
  } catch (error: unknown) {
    errorMessage.value = parseError(error)
    messages.value.push({
      id: createId(),
      role: 'bot',
      text: '죄송합니다. 서버와 통신 중 오류가 발생했습니다.',
      timestamp: Date.now()
    })
  } finally {
    isLoading.value = false
    chatInputRef.value?.clearInput()
  }
}

const resetConversation = async () => {
  messages.value = [buildWelcomeMessage()]
  chatInputRef.value?.clearInput()

  try {
    const response = await callBackend<{ session_id: string }>('/api/reset', {
      session_id: sessionId.value ?? undefined
    })
    sessionId.value = response?.session_id ?? null
  } catch (error) {
    errorMessage.value = '세션 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.'
  }
}

const parseError = (error: unknown) => {
  if (typeof error === 'string') {
    return error
  }
  if (error && typeof error === 'object') {
    const anyError = error as Record<string, any>
    if (anyError?.data?.detail) {
      return anyError.data.detail
    }
    if (anyError?.statusMessage) {
      return anyError.statusMessage
    }
  }
  return '요청 처리 중 문제가 발생했습니다.'
}

useHead({
  title: 'Factory Chatbot',
  meta: [
    {
      name: 'description',
      content: '서울 공장 등록 현황 데이터를 활용하는 챗봇 인터페이스'
    }
  ]
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(135deg, #e0f2fe, #f5f5f5);
  display: flex;
  justify-content: center;
  align-items: stretch;
  padding: 0;
}

.chat-card {
  width: 100%;
  max-width: 960px;
  height: 100vh;
  background: #fff;
  border-radius: 0;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

@media (min-width: 768px) {
  .page {
    padding: 0 2rem;
  }

  .chat-card {
    border-radius: 24px;
    box-shadow: 0 20px 60px rgba(15, 23, 42, 0.1);
  }
}

.messages-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: linear-gradient(#f8fafc, #f1f5f9);
  padding-bottom: 7rem;
}

.error-banner {
  margin: 0 1.5rem;
  padding: 0.75rem 1rem;
  background: #fee2e2;
  border: 1px solid #fecaca;
  color: #991b1b;
  border-radius: 12px;
  font-size: 0.95rem;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>