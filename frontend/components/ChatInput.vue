<template>
  <form class="chat-input" @submit.prevent="handleSubmit">
    <div class="input-wrapper">
      <textarea
        v-model="message"
        rows="2"
        placeholder="예) 서울에서 전자부품 업종의 공장 수를 알려줘"
        @keydown="handleKeydown"
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
import { ref } from 'vue'

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

const handleSubmit = () => {
  const content = message.value.trim()
  if (!content || props.disabled) {
    return
  }
  emit('submit', content)
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
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
  padding: 1rem 2rem 3rem 2rem;
  background: #fff;
  position: sticky;
  bottom: 0;
  z-index: 5;
}

.input-wrapper {
  position: relative;
}

textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 0.9rem 3.25rem 0.9rem 1rem;
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
  top: 50%;
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

