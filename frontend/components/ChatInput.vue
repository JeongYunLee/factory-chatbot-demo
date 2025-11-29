<template>
  <form class="chat-input" @submit.prevent="handleSubmit">
    <div class="example-chips-container">
      <button
        v-if="showLeftButton"
        type="button"
        class="scroll-button scroll-button-left"
        :disabled="disabled"
        @click="scrollLeft"
        aria-label="왼쪽으로 스크롤"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <div
        ref="scrollContainerRef"
        class="example-chips-scroll"
        @wheel="handleWheel"
      >
        <button
          v-for="(example, index) in exampleQuestions"
          :key="index"
          type="button"
          class="example-chip"
          :disabled="disabled"
          @click="handleExampleClick(example)"
        >
          {{ example }}
        </button>
      </div>
      <button
        v-if="showRightButton"
        type="button"
        class="scroll-button scroll-button-right"
        :disabled="disabled"
        @click="scrollRight"
        aria-label="오른쪽으로 스크롤"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </button>
    </div>
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="message"
        rows="2"
        placeholder="예) 서울에서 전자부품 업종의 공장 수를 알려줘"
        @keydown="handleKeydown"
        @input="handleInput"
      />
      <button
        class="send-btn"
        type="submit"
        :disabled="disabled || !message.trim()"
        aria-label="메시지 전송"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M3.4 20.6 21 12 3.4 3.4 3 10l11 2-11 2z"
          />
        </svg>
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
  }>(),
  {
    disabled: false
  }
)

const emit = defineEmits<{
  submit: [string]
}>()

const message = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const scrollContainerRef = ref<HTMLElement | null>(null)
const showLeftButton = ref(false)
const showRightButton = ref(false)

const exampleQuestions = [
  '서울에서 공장이 가장 많은 구는?',
  '지난 20년간 서울에서 공장 수가 가장 많이 증가한 5개 구를 알려줘',
  '외국인 근로자가 많은 공장은?',
  '최근 5년간 서울 전체 공장 등록 건수 추이를 보여줘'
]

const handleExampleClick = async (exampleText: string) => {
  if (props.disabled) return
  
  // 예제 텍스트를 입력창에 설정
  message.value = exampleText
  await nextTick()
  
  // 자동으로 제출
  const actualContent = textareaRef.value?.value || exampleText
  const contentToSend = actualContent.endsWith(' ') ? actualContent : actualContent + ' '
  emit('submit', contentToSend)
}

const handleWheel = (event: WheelEvent) => {
  if (!scrollContainerRef.value) return
  
  // 마우스 휠을 가로 스크롤로 변환
  event.preventDefault()
  scrollContainerRef.value.scrollLeft += event.deltaY
}

const scrollLeft = () => {
  if (!scrollContainerRef.value) return
  scrollContainerRef.value.scrollBy({ left: -200, behavior: 'smooth' })
}

const scrollRight = () => {
  if (!scrollContainerRef.value) return
  scrollContainerRef.value.scrollBy({ left: 200, behavior: 'smooth' })
}

const checkScrollButtons = () => {
  if (!scrollContainerRef.value) return
  
  const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.value
  showLeftButton.value = scrollLeft > 0
  showRightButton.value = scrollLeft < scrollWidth - clientWidth - 1
}

let resizeObserver: ResizeObserver | null = null

onMounted(async () => {
  await nextTick()
  if (scrollContainerRef.value) {
    checkScrollButtons()
    scrollContainerRef.value.addEventListener('scroll', checkScrollButtons)
    
    // ResizeObserver로 컨테이너 크기 변경 감지
    resizeObserver = new ResizeObserver(() => {
      checkScrollButtons()
    })
    resizeObserver.observe(scrollContainerRef.value)
  }
})

onUnmounted(() => {
  if (scrollContainerRef.value) {
    scrollContainerRef.value.removeEventListener('scroll', checkScrollButtons)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})

const handleInput = (event: Event) => {
  // input 이벤트에서 실제 DOM 값을 동기화하여 마지막 입력 보존
  const target = event.target as HTMLTextAreaElement
  if (target.value !== message.value) {
    message.value = target.value
  }
}

const handleSubmit = async () => {
  // Vue 반응성 업데이트를 기다린 후, 실제 DOM에서 직접 값을 읽어서 마지막 글자 보존
  await nextTick()
  
  // 실제 DOM element에서 직접 값을 읽어서 마지막 입력이 확실히 포함되도록 함
  const actualContent = textareaRef.value?.value || message.value
  
  // 빈 메시지 체크만 수행 (공백만 있는 경우)
  if (!actualContent.trim() || props.disabled) {
    return
  }
  
  // 마지막 글자가 잘리는 것을 방지하기 위해 끝에 빈 스페이스 추가
  const contentToSend = actualContent.endsWith(' ') ? actualContent : actualContent + ' '
  
  // 디버깅: 전송 전 메시지 확인
  console.log('📤 전송 메시지:', {
    DOM값길이: textareaRef.value?.value?.length || 0,
    반응값길이: message.value.length,
    실제사용값: actualContent.length,
    실제사용끝5자: actualContent.slice(-5),
    전송길이: contentToSend.length,
    전송끝5자: contentToSend.slice(-5)
  })
  
  emit('submit', contentToSend)
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    // preventDefault로 엔터 입력 방지
    event.preventDefault()
    
    // requestAnimationFrame을 사용하여 브라우저가 DOM을 업데이트한 후 실제 값을 읽음
    // 이렇게 하면 마지막 입력된 글자가 포함된 값을 읽을 수 있음
    requestAnimationFrame(() => {
      requestAnimationFrame(async () => {
        // 이중 requestAnimationFrame으로 DOM 업데이트가 완전히 완료되도록 보장
        await nextTick()
        
        // 실제 DOM element에서 직접 값을 읽어서 마지막 글자 보존
        const textarea = textareaRef.value
        if (textarea) {
          const actualValue = textarea.value
          // DOM 값이 반응성 값과 다르면 DOM 값을 사용
          if (actualValue !== message.value) {
            message.value = actualValue
            await nextTick()
          }
        }
        
        handleSubmit()
      })
    })
  }
}

const clearInput = () => {
  message.value = ''
}

defineExpose({
  clearInput
})
</script>

<style scoped>
.chat-input {
  border-top: 1px solid #e5e7eb;
  padding: 1rem 2rem 2.2rem 2rem;
  background: #fff;
  position: sticky;
  bottom: 0;
  z-index: 5;
}

.example-chips-container {
  margin-bottom: 0.75rem;
  padding: 0 0.25rem;
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.example-chips-scroll {
  flex: 1;
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  padding-bottom: 0.25rem;
}

.scroll-button {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  padding: 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.scroll-button:hover:not(:disabled) {
  background: #f3f4f6;
  border-color: #d1d5db;
  color: #4b5563;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.scroll-button:active:not(:disabled) {
  transform: scale(0.95);
}

.scroll-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.scroll-button svg {
  width: 16px;
  height: 16px;
  stroke: currentColor;
}

.example-chips-scroll::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}

.example-chip {
  flex-shrink: 0;
  padding: 0.5rem 0.875rem;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  font-size: 0.8125rem;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  font-family: inherit;
}

.example-chip:hover:not(:disabled) {
  background: #e5e7eb;
  border-color: #d1d5db;
  color: #4b5563;
}

.example-chip:active:not(:disabled) {
  background: #d1d5db;
  transform: scale(0.98);
}

.example-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-wrapper {
  position: relative;
}

textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 0.9rem 3.25rem 0.9rem 0.9rem;
  box-sizing: border-box;
  font-size: 1rem;
  resize: none;
  transition: border-color 0.2s ease;
  font-family: inherit;
}

textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2);
}

.send-btn {
  position: absolute;
  top: 48%;
  right: 0.6rem;
  transform: translateY(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #111827;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease;
  color: #fff;
  padding: 0;
}

.send-btn svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  opacity: 0.85;
}

.send-btn:not(:disabled):active {
  transform: translateY(-50%) scale(0.96);
}
</style>

