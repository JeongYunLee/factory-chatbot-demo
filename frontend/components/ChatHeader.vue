<template>
  <header class="chat-header">
    <div>
      <p class="eyebrow">Data Insight Chatbot</p>
      <br></br>
      <h1>데이터 기반 챗봇 어시스턴트</h1>
      <p class="subtitle">
        <!-- 서울 지역 공장 등록 현황 데이터를 기반으로 자연어 질문에 답변합니다. -->
      </p>
    </div>

    <div class="actions">
      <div class="status">
        <span class="status-dot" :class="{ online: isOnline }"></span>
        <span>{{ isLoading ? '답변 생성 중...' : '대기 중' }}</span>
      </div>
      <!-- <p v-if="sessionId" class="session">세션 ID: {{ shortSessionId }}</p> -->
      <button class="ghost-btn" @click="$emit('reset')">
        대화 초기화
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  sessionId?: string | null
  isLoading: boolean
}>()

defineEmits<{
  reset: []
}>()

const isOnline = computed(() => !props.isLoading)
const shortSessionId = computed(() =>
  props.sessionId ? props.sessionId.slice(0, 8) + '…' : '미생성'
)
</script>

<style scoped>
.chat-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid #ececec;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 5;
}

@media (min-width: 768px) {
  .chat-header {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
  }
}

.eyebrow {
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #888;
  margin-bottom: 0.2rem;
}

h1 {
  font-size: 1.6rem;
  margin: 0;
  color: #111;
}

.subtitle {
  margin: 0.4rem 0 0;
  color: #555;
  font-size: 0.95rem;
}

.actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.6rem;
}

@media (min-width: 768px) {
  .actions {
    align-items: flex-end;
  }
}

.status {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 600;
  color: #333;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #bbb;
}

.status-dot.online {
  background: #4caf50;
  box-shadow: 0 0 6px rgba(76, 175, 80, 0.65);
}

.session {
  font-size: 0.85rem;
  color: #666;
}

.ghost-btn {
  padding: 0.4rem 0.9rem;
  border: 1px solid #d0d0d0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s ease;
}

.ghost-btn:hover {
  border-color: #222;
  color: #222;
}
</style>

