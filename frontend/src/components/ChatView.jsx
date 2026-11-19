import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Mic,
  Volume2,
  VolumeX,
  History,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Terminal,
} from 'lucide-react';
import { api } from '../api';

export default function ChatView({
  conversations,
  activeConversationId,
  setActiveConversationId,
  refreshConversations,
  onNotify,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [speakResponse, setSpeakResponse] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef(null);

  // Load active conversation messages
  useEffect(() => {
    if (!activeConversationId) return;
    loadConversationMessages(activeConversationId);
  }, [activeConversationId]);

  const loadConversationMessages = async (id) => {
    try {
      const data = await api.getConversation(id);
      setMessages(data.messages || []);
    } catch (err) {
      console.error(err);
      onNotify('Failed to load conversation history', 'error');
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    // Optimistic UI update
    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.sendChat(text, activeConversationId, speakResponse);
      if (!activeConversationId && res.conversation_id) {
        setActiveConversationId(res.conversation_id);
        refreshConversations();
      }

      const assistantMsg = {
        id: `resp-${Date.now()}`,
        role: 'assistant',
        content: res.message,
        response_type: res.response_type,
        detected_intent: res.detected_intent,
        required_tools: res.required_tools,
        execution_plan: res.execution_plan,
        requires_confirmation: res.requires_confirmation,
        spoken: res.spoken,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      onNotify(err.message || 'Failed to get response', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceInput = async () => {
    if (isRecording) return;
    setIsRecording(true);
    onNotify('Listening... speak now into your microphone', 'info');
    try {
      const res = await api.voiceListen(5.0);
      if (res.transcript) {
        setInput(res.transcript);
        onNotify(`Transcribed: "${res.transcript}"`, 'success');
      } else {
        onNotify('No speech detected. Try again.', 'warning');
      }
    } catch (err) {
      onNotify('Microphone or transcription error', 'error');
    } finally {
      setIsRecording(false);
    }
  };

  const handleDeleteConversation = async (id, e) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(id);
      refreshConversations();
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
      onNotify('Conversation deleted', 'info');
    } catch (err) {
      onNotify('Failed to delete conversation', 'error');
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
        {/* Header Bar */}
        <div style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => setShowHistory(!showHistory)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 10px',
                borderRadius: '6px',
                background: showHistory ? 'var(--bg-tertiary)' : 'transparent',
                border: '1px solid var(--border-color)',
                fontSize: '12px',
                color: 'var(--text-main)',
              }}
            >
              <History size={14} />
              <span>History</span>
            </button>
            <div style={{ fontWeight: 600, fontSize: '14px' }}>
              {activeConversationId
                ? (conversations.find((c) => c.id === activeConversationId)?.title || 'Conversation')
                : 'New Assistant Session'}
            </div>
          </div>

          {/* Voice Speak Response Toggle */}
          <button
            onClick={() => setSpeakResponse(!speakResponse)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '6px',
              backgroundColor: speakResponse ? 'rgba(6, 182, 212, 0.15)' : 'var(--bg-tertiary)',
              border: `1px solid ${speakResponse ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
              color: speakResponse ? 'var(--accent-cyan)' : 'var(--text-muted)',
              fontSize: '12px',
            }}
          >
            {speakResponse ? <Volume2 size={14} /> : <VolumeX size={14} />}
            <span>Speak Responses</span>
          </button>
        </div>

        {/* Message Thread */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 28px',
          display: 'flex',
          flexDirection: 'column',
          gap: '18px',
        }}>
          {messages.length === 0 && (
            <div style={{
              margin: 'auto',
              textAlign: 'center',
              maxWidth: '480px',
              padding: '32px',
              color: 'var(--text-muted)',
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px auto',
                color: '#fff',
                fontWeight: 700,
                fontSize: '22px',
              }}>
                N
              </div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#fff', marginBottom: '8px' }}>
                How can NOVA help you today?
              </h2>
              <p style={{ fontSize: '13px', lineHeight: 1.6, marginBottom: '20px' }}>
                Ask questions, automate desktop workflows, explore downloaded files, search web content, or run system tasks locally.
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}>
                {[
                  'What is my system resource usage?',
                  'Search memories for my preferences',
                  'Test voice speech synthesis',
                  'List files in my downloads folder',
                ].map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(prompt)}
                    style={{
                      padding: '8px 12px',
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '16px',
                      fontSize: '12px',
                      color: 'var(--text-main)',
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.id || idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start',
                  width: '100%',
                }}
              >
                <div style={{
                  maxWidth: '75%',
                  padding: '14px 18px',
                  borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  backgroundColor: isUser ? 'var(--accent-blue)' : 'var(--bg-card)',
                  border: isUser ? 'none' : '1px solid var(--border-color)',
                  color: '#fff',
                  fontSize: '13.5px',
                  lineHeight: 1.55,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                }}>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                  {/* Metadata cards for assistant messages */}
                  {!isUser && (msg.required_tools?.length > 0 || msg.execution_plan?.length > 0) && (
                    <div style={{
                      marginTop: '12px',
                      paddingTop: '10px',
                      borderTop: '1px solid rgba(255,255,255,0.1)',
                      fontSize: '11.5px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                    }}>
                      {msg.required_tools?.length > 0 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-cyan)' }}>
                          <Terminal size={12} />
                          <span>Tools Required: {msg.required_tools.join(', ')}</span>
                        </div>
                      )}
                      {msg.execution_plan?.length > 0 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-amber)' }}>
                          <Layers size={12} />
                          <span>Execution Steps Planned: {msg.execution_plan.length}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div style={{
                  fontSize: '10.5px',
                  color: 'var(--text-muted)',
                  marginTop: '4px',
                  marginRight: isUser ? '4px' : '0',
                  marginLeft: !isUser ? '4px' : '0',
                }}>
                  {isUser ? 'You' : 'NOVA'} • {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            );
          })}

          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '13px' }}>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: 'var(--accent-cyan)',
                animation: 'pulse 1s infinite',
              }} />
              <span>NOVA is thinking...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div style={{
          padding: '16px 20px',
          backgroundColor: 'var(--bg-secondary)',
          borderTop: '1px solid var(--border-subtle)',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '6px 12px',
            gap: '8px',
          }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask NOVA anything or request a task... (Press Enter to send)"
              rows={1}
              style={{
                flex: 1,
                border: 'none',
                background: 'transparent',
                resize: 'none',
                maxHeight: '120px',
                fontSize: '13.5px',
                lineHeight: 1.4,
              }}
            />

            {/* Voice Dictation Button */}
            <button
              onClick={handleVoiceInput}
              disabled={isRecording}
              title="Speak message"
              style={{
                padding: '8px',
                borderRadius: '8px',
                backgroundColor: isRecording ? 'rgba(244, 63, 94, 0.2)' : 'transparent',
                color: isRecording ? 'var(--accent-rose)' : 'var(--text-muted)',
              }}
            >
              <Mic size={18} />
            </button>

            {/* Send Button */}
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              style={{
                padding: '8px 12px',
                borderRadius: '8px',
                backgroundColor: input.trim() && !loading ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
                color: input.trim() && !loading ? '#fff' : 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* Slide-out Conversation History Drawer */}
      {showHistory && (
        <div style={{
          width: '280px',
          backgroundColor: 'var(--bg-secondary)',
          borderLeft: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
        }}>
          <div style={{
            padding: '16px',
            borderBottom: '1px solid var(--border-subtle)',
            fontWeight: 600,
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <span>Saved Conversations</span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{conversations.length}</span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => {
                  setActiveConversationId(c.id);
                  setShowHistory(false);
                }}
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  backgroundColor: activeConversationId === c.id ? 'var(--bg-tertiary)' : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '4px',
                }}
              >
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{
                    fontSize: '12.5px',
                    fontWeight: 500,
                    textOverflow: 'ellipsis',
                    overflow: 'hidden',
                    whiteSpace: 'nowrap',
                  }}>
                    {c.title}
                  </div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {c.message_count} messages
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(c.id, e)}
                  title="Delete conversation"
                  style={{
                    padding: '4px',
                    color: 'var(--text-muted)',
                    marginLeft: '6px',
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
