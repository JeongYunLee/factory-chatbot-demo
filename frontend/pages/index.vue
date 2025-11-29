<template>
  <div class="page">
    <div class="workspace">
      <div class="chat-card">
        <ChatHeader
          :session-id="sessionId"
          :is-loading="isLoading"
          @reset="resetConversation"
        />

        <div class="messages-container" ref="messageContainer">
          <ChatMessageList
            :messages="messages"
            :is-loading="isLoading"
            @show-data="handleDataRequest"
          />
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

      <Transition name="slide">
        <aside v-if="isPanelOpen" class="data-panel">
          <div class="panel-header">
            <div class="panel-header-content">
              <p class="panel-title">데이터 기반 결과</p>
              <p class="panel-subtitle">실행 코드와 출력 결과를 확인하세요.</p>
            </div>
            <button class="panel-close-button" @click="closePanel" aria-label="패널 닫기">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <div v-if="executionDetail && executionDetail.result?.type === 'table'" class="panel-tabs">
            <button
              class="tab-button"
              :class="{ active: activeTab === 'data' }"
              @click="activeTab = 'data'"
            >
              데이터
            </button>
            <button
              v-if="executionDetail.result?.visualization && executionDetail.result.visualization.chart_type !== 'none'"
              class="tab-button"
              :class="{ active: activeTab === 'visualization' }"
              @click="activeTab = 'visualization'"
            >
              시각화
            </button>
          </div>

          <div class="panel-body">
            <div v-if="!selectedExecutionId" class="panel-placeholder">
              데이터 기반 답변 버튼을 누르면 실행 코드와 결과가 이곳에 표시됩니다.
            </div>

            <div v-else-if="isExecutionLoading" class="panel-placeholder">
              실행 결과를 불러오는 중입니다...
            </div>

            <div v-else-if="executionError" class="panel-placeholder error">
              {{ executionError }}
            </div>

            <div v-else-if="executionDetail" class="panel-content">
              <section class="panel-section">
                <p class="section-label">실행 코드</p>
                <div class="code-block-wrapper">
                  <button
                    class="code-copy-button"
                    @click="copyToClipboard(executionDetail.code ?? '코드 정보를 찾을 수 없습니다.')"
                    :aria-label="'코드 복사'"
                  >
                    <svg v-if="!copiedStates.code" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </button>
                  <pre class="code-block">
<code>{{ executionDetail.code ?? '코드 정보를 찾을 수 없습니다.' }}</code>
                  </pre>
                </div>
              </section>

              <!-- 데이터 탭 -->
              <section v-if="activeTab === 'data'" class="panel-section">
                <p class="section-label">출력 결과</p>
                <template
                  v-if="
                    executionDetail.result?.type === 'table' &&
                    executionDetail.result?.rows?.length
                  "
                >
                  <div class="table-wrapper">
                    <table class="data-table">
                      <thead>
                        <tr>
                          <th
                            v-for="column in executionDetail.result.columns ?? []"
                            :key="column"
                          >
                            {{ column }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(row, rowIndex) in executionDetail.result.rows"
                          :key="rowIndex"
                        >
                          <td
                            v-for="column in executionDetail.result.columns ?? []"
                            :key="column"
                          >
                            {{ formatCellValue(row[column]) }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p class="row-count">
                    총 {{ executionDetail.result.row_count }}행 중
                    {{ executionDetail.result.rows.length }}행 표시
                  </p>
                </template>

                <template v-else>
                  <div class="code-block-wrapper">
                    <button
                      class="code-copy-button"
                      @click="copyToClipboard(fallbackResultText, 'result')"
                      :aria-label="'결과 복사'"
                    >
                      <svg v-if="!copiedStates.result" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                      </svg>
                      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                    </button>
                    <pre class="code-block">
<code>{{ fallbackResultText }}</code>
                    </pre>
                  </div>
                </template>
              </section>

              <!-- 시각화 탭 -->
              <section v-if="activeTab === 'visualization'" class="panel-section">
                <p class="section-label">시각화</p>
                <VisualizationPanel
                  v-if="executionDetail.result?.type === 'table' && executionDetail.result.rows"
                  :data="executionDetail.result.rows"
                  :visualization-meta="executionDetail.result.visualization"
                />
              </section>
            </div>
          </div>
        </aside>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import ChatHeader from '~/components/ChatHeader.vue'
import ChatMessageList, { type ChatMessage } from '~/components/ChatMessageList.vue'
import ChatInput from '~/components/ChatInput.vue'
import VisualizationPanel from '~/components/VisualizationPanel.vue'

interface ApiResponse {
  answer: string
  session_id: string
  status: string
  message_count?: number
  error_type?: string
  execution_id?: string | null
}

interface VisualizationMeta {
  chart_type: string
  x_axis?: string | null
  y_axis?: string | null
  orientation?: string | null
  has_location?: boolean
  group_by?: string | null
  time_series?: boolean
}

interface ExecutionResultPayload {
  type: 'table' | 'list' | 'object' | 'text'
  columns?: string[]
  rows?: Array<Record<string, any>>
  row_count?: number
  data?: Record<string, any>
  value?: string | number | null
  visualization?: VisualizationMeta | null
}

interface ExecutionResultResponse {
  execution_id: string
  session_id: string
  code?: string | null
  result?: ExecutionResultPayload
  created_at?: number
}

const config = useRuntimeConfig()
const baseURL = String(config.public.apiUrl ?? '')

const sessionId = useState<string | null>('factory-session', () => null)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

const createId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const buildWelcomeMessage = (): ChatMessage => ({
  id: createId(),
  role: 'bot',
  text: '안녕하세요! 데이터를 기반으로 질문을 도와드리는 챗봇입니다. 궁금한 점을 자연어로 물어보세요.',
  timestamp: Date.now(),
  hasData: false
})

const messages = ref<ChatMessage[]>([buildWelcomeMessage()])
const chatInputRef = ref<InstanceType<typeof ChatInput> | null>(null)
const messageContainer = ref<HTMLElement | null>(null)
const selectedExecutionId = ref<string | null>(null)
const executionDetail = ref<ExecutionResultResponse | null>(null)
const isExecutionLoading = ref(false)
const executionError = ref<string | null>(null)
const copiedStates = ref({ code: false, result: false })
const activeTab = ref<'data' | 'visualization'>('data')

const isPanelOpen = computed(() => selectedExecutionId.value !== null)

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

const sendMessage = async (content: string) => {
  if (!content.trim() || isLoading.value) return

  messages.value.push({
    id: createId(),
    role: 'user',
    text: content,
    timestamp: Date.now(),
    hasData: false
  })

  isLoading.value = true
  errorMessage.value = null

  try {
    const responseRaw = await fetch(`${baseURL}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: content,
        session_id: sessionId.value ?? undefined
      })
    })

    if (!responseRaw.ok) {
      throw new Error(`HTTP ${responseRaw.status}`)
    }

    const response: ApiResponse = await responseRaw.json()

    if (response.session_id) {
      sessionId.value = response.session_id
    }

    // [DATA] 접두사 제거 및 hasData 플래그 설정
    let answerText = response.answer ?? '응답을 받을 수 없습니다.'
    const hasDataPrefix = answerText.startsWith('[DATA]')
    if (hasDataPrefix) {
      answerText = answerText.replace(/^\[DATA\]\s*/, '')
    }
    const executionId = response.execution_id ?? null
    const hasData = Boolean(executionId)

    // 시각화 데이터 가져오기
    let visualizationData: Array<Record<string, any>> | null = null
    let visualizationMeta: VisualizationMeta | null = null

    if (executionId) {
      try {
        const executionResponse = await fetch(`${baseURL}execution/${executionId}`)
        if (executionResponse.ok) {
          const executionDetail = (await executionResponse.json()) as ExecutionResultResponse
          if (
            executionDetail.result?.type === 'table' &&
            executionDetail.result.rows &&
            executionDetail.result.visualization &&
            executionDetail.result.visualization.chart_type !== 'none'
          ) {
            visualizationData = executionDetail.result.rows
            visualizationMeta = executionDetail.result.visualization
          }
        }
      } catch (error) {
        console.error('시각화 데이터 로드 실패:', error)
      }
    }

    messages.value.push({
      id: createId(),
      role: 'bot',
      text: answerText,
      timestamp: Date.now(),
      hasData,
      executionId,
      visualizationData,
      visualizationMeta
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
  selectedExecutionId.value = null
  executionDetail.value = null
  executionError.value = null
  isExecutionLoading.value = false

  try {
    const responseRaw = await fetch(`${baseURL}reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value ?? undefined
      })
    })
    const response = await responseRaw.json()
    sessionId.value = response?.session_id ?? null
  } catch (error) {
    errorMessage.value = '세션 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.'
  }
}

const parseError = (error: unknown) => {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error !== null) {
    const e = error as Record<string, any>
    if (e?.data?.detail) return e.data.detail
    if (e?.statusMessage) return e.statusMessage
  }
  return '요청 처리 중 문제가 발생했습니다.'
}

const handleDataRequest = async (executionId: string | null | undefined) => {
  if (!executionId) return
  if (selectedExecutionId.value === executionId && executionDetail.value) {
    return
  }

  selectedExecutionId.value = executionId
  executionDetail.value = null
  executionError.value = null
  isExecutionLoading.value = true
  activeTab.value = 'data' // 탭 초기화

  try {
    const response = await fetch(`${baseURL}execution/${executionId}`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    executionDetail.value = (await response.json()) as ExecutionResultResponse
    // 시각화 메타데이터가 있으면 시각화 탭으로 자동 전환
    if (executionDetail.value?.result?.visualization && 
        executionDetail.value.result.visualization.chart_type !== 'none') {
      activeTab.value = 'visualization'
    }
  } catch (error) {
    executionError.value = parseError(error)
  } finally {
    isExecutionLoading.value = false
  }
}

const closePanel = () => {
  selectedExecutionId.value = null
  executionDetail.value = null
  executionError.value = null
  isExecutionLoading.value = false
  activeTab.value = 'data'
}

const formatCellValue = (value: unknown) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') {
    return Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

const fallbackResultText = computed(() => {
  const result = executionDetail.value?.result
  if (!result) {
    return '표시할 데이터가 없습니다.'
  }

  if (result.type === 'text') {
    return result.value ? String(result.value) : '표시할 데이터가 없습니다.'
  }

  if (result.type === 'list') {
    return JSON.stringify(result.rows ?? [], null, 2)
  }

  if (result.type === 'object') {
    return JSON.stringify(result.data ?? {}, null, 2)
  }

  if (result.type === 'table' && !result.rows?.length) {
    return '표시할 데이터가 없습니다.'
  }

  return JSON.stringify(result, null, 2)
})

const copyToClipboard = async (text: string, type: 'code' | 'result' = 'code') => {
  try {
    await navigator.clipboard.writeText(text)
    copiedStates.value[type] = true
    setTimeout(() => {
      copiedStates.value[type] = false
    }, 2000)
  } catch (error) {
    console.error('복사 실패:', error)
  }
}

useHead({
  title: 'Data Chatbot',
  meta: [
    {
      name: 'description',
      content: '데이터를 활용하는 챗봇 서비스'
    }
  ]
})
</script>
