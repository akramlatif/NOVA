/**
 * NOVA API Client — Localhost FastAPI bridge.
 */

const BASE_URL = '/api';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP Error ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

export const api = {
  // System & Health
  getHealth: () => request('/health'),
  getSystemStatus: () => request('/system/status'),

  // Conversations & Chat
  getConversations: () => request('/conversations'),
  createConversation: (title) => request('/conversations', { method: 'POST', body: JSON.stringify({ title }) }),
  getConversation: (id) => request(`/conversations/${id}`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: 'DELETE' }),
  sendChat: (message, conversation_id, speak_response = false) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id, speak_response }),
    }),

  // Tasks & Approvals
  getTasks: () => request('/tasks'),
  submitTask: (instruction, auto_execute = true) =>
    request('/tasks', {
      method: 'POST',
      body: JSON.stringify({ instruction, auto_execute }),
    }),
  cancelTask: (taskId) => request(`/tasks/${taskId}/cancel`, { method: 'POST' }),
  getApprovals: () => request('/approvals'),
  decideApproval: (id, approved) =>
    request(`/approvals/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    }),

  // Memory & Preferences
  getMemories: (query, category) => {
    const params = new URLSearchParams();
    if (query) params.append('query', query);
    if (category) params.append('category', category);
    const qs = params.toString();
    return request(`/memory${qs ? `?${qs}` : ''}`);
  },
  addMemory: (key, content, category = 'fact') =>
    request('/memory', {
      method: 'POST',
      body: JSON.stringify({ key, content, category }),
    }),
  deleteMemory: (key) => request(`/memory/${key}`, { method: 'DELETE' }),
  getPreferences: (category) => {
    const qs = category ? `?category=${category}` : '';
    return request(`/preferences${qs}`);
  },
  setPreference: (key, value, category = 'ui') =>
    request('/preferences', {
      method: 'POST',
      body: JSON.stringify({ key, value, category }),
    }),

  // Voice
  getVoiceStatus: () => request('/voice/status'),
  voiceSpeak: (text, rate, voice_index) =>
    request('/voice/speak', {
      method: 'POST',
      body: JSON.stringify({ text, rate, voice_index }),
    }),
  voiceListen: (duration = 5.0) =>
    request('/voice/listen', {
      method: 'POST',
      body: JSON.stringify({ duration, adjust_noise: false }),
    }),
  toggleWakeWord: (enabled, consent = false) =>
    request('/voice/wakeword', {
      method: 'POST',
      body: JSON.stringify({ enabled, consent }),
    }),

  // Downloads & Settings
  getDownloads: () => request('/downloads'),
  getSettings: () => request('/settings'),
  updateSettings: (settings) =>
    request('/settings', {
      method: 'POST',
      body: JSON.stringify(settings),
    }),
};
