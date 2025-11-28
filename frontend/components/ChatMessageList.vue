<template>
  <div class="message-list">
    <div
      v-for="message in messages"
      :key="message.id"
      class="bubble-row"
      :class="message.role"
    >
      <div class="avatar" :class="message.role">
        <svg v-if="message.role === 'user'" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 12c4.418 0 8 2.239 8 5v1H4v-1c0-2.761 3.582-5 8-5Z"
          />
        </svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3c3.866 0 7 2.239 7 5v4c0 2.761-3.134 5-7 5s-7-2.239-7-5V8c0-2.761 3.134-5 7-5Zm0 0c-.552 0-1 .671-1 1.5S11.448 6 12 6s1-.671 1-1.5S12.552 3 12 3Zm-3 15h6l3 3H6l3-3Z"
          />
        </svg>
      </div>
      <div class="bubble">
        <button
          v-if="message.role === 'bot' && message.hasData && message.executionId"
          class="data-button"
          @click="emit('show-data', message.executionId)"
        >
          데이터 기반 답변
        </button>
        <div
          class="bubble-text"
          :class="{ 'has-data-button': message.role === 'bot' && message.hasData }"
          v-html="renderMarkdown(message.text)"
        />
      </div>
    </div>

    <div v-if="isLoading" class="bubble-row bot">
      <div class="avatar bot typing-avatar">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3c3.866 0 7 2.239 7 5v4c0 2.761-3.134 5-7 5s-7-2.239-7-5V8c0-2.761 3.134-5 7-5Zm0 0c-.552 0-1 .671-1 1.5S11.448 6 12 6s1-.671 1-1.5S12.552 3 12 3Zm-3 15h6l3 3H6l3-3Z"
          />
        </svg>
      </div>
      <div class="bubble typing">
        <span class="dot" v-for="index in 3" :key="index"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import MarkdownIt from 'markdown-it'

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  timestamp: number
  hasData?: boolean
  executionId?: string | null
}

defineProps<{
  messages: ChatMessage[]
  isLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'show-data', executionId: string | null | undefined): void
}>()

const md = new MarkdownIt({
  breaks: true,
  linkify: true
})

const renderMarkdown = (text: string) => md.render(text ?? '')
</script>

<style scoped>
.message-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
}

.bubble-row {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.bubble-row.user {
  flex-direction: row-reverse;
}

.bubble {
  max-width: min(640px, 85vw);
  border-radius: 18px;
  padding: 0.9rem 1.1rem;
  background: #f1f5f9;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
  position: relative;
}

.data-button {
  position: absolute;
  top: -0.5rem;
  left: 0.5rem;
  padding: 0.4rem 0.8rem;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;
  z-index: 1;
}

.data-button:hover {
  background: #1d4ed8;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.data-button:active {
  transform: translateY(0);
}

.bubble-row.user .bubble {
  background: #2563eb;
  color: #fff;
}

.bubble-text :deep(p) {
  margin: 0 0 0.6rem;
  line-height: 1.6;
}

.bubble-text.has-data-button {
  padding-top: 0.5rem;
}

.bubble-text :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble-text :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  padding: 0.1rem 0.4rem;
  border-radius: 6px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
}

.bubble-text :deep(pre) {
  background: rgba(15, 23, 42, 0.8);
  padding: 0.8rem;
  border-radius: 12px;
  overflow: auto;
}

.bubble-text :deep(a) {
  color: inherit;
  text-decoration: underline;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar svg {
  width: 22px;
  height: 22px;
  fill: #1f2937;
}

.avatar.user {
  background: #dbeafe;
}

.avatar.bot {
  background: #fee2e2;
}

.bubble-row.user .avatar svg {
  fill: #1d4ed8;
}

.bubble-row.bot .avatar svg {
  fill: #be123c;
}

.typing {
  display: inline-flex;
  gap: 0.3rem;
  background: #fff;
  border: 1px solid #dbeafe;
}

.typing-avatar {
  background: #fee2e2;
}

.dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  background: #2563eb;
  animation: blink 1.2s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation-delay: 0.15s;
}

.dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0;
    transform: translateY(0);
  }
  40% {
    opacity: 0.8;
    transform: translateY(-2px);
  }
}
</style>

