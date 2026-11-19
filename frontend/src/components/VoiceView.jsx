import React, { useState, useEffect } from 'react';
import {
  Mic,
  Volume2,
  Sliders,
  ShieldCheck,
  ShieldAlert,
  Radio,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { api } from '../api';

export default function VoiceView({ onNotify }) {
  const [status, setStatus] = useState(null);
  const [testText, setTestText] = useState('Hello! NOVA local voice assistant is online and ready.');
  const [speechRate, setSpeechRate] = useState(175);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [showConsentModal, setShowConsentModal] = useState(false);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const data = await api.getVoiceStatus();
      setStatus(data);
      if (data?.speech_rate) setSpeechRate(data.speech_rate);
    } catch (err) {
      console.error(err);
    }
  };

  const handleTestSpeak = async () => {
    if (!testText.trim() || isSpeaking) return;
    setIsSpeaking(true);
    try {
      await api.voiceSpeak(testText, speechRate);
      onNotify('Speech synthesized via Windows SAPI5', 'success');
    } catch (err) {
      onNotify('Failed to synthesize speech', 'error');
    } finally {
      setIsSpeaking(false);
    }
  };

  const handleRecord = async () => {
    if (isListening) return;
    setIsListening(true);
    setTranscript('');
    onNotify('Recording microphone for 5 seconds...', 'info');
    try {
      const res = await api.voiceListen(5.0);
      if (res.transcript) {
        setTranscript(res.transcript);
        onNotify(`Transcribed: "${res.transcript}"`, 'success');
      } else {
        onNotify('No speech detected in audio stream', 'warning');
      }
    } catch (err) {
      onNotify('Microphone or STT error', 'error');
    } finally {
      setIsListening(false);
    }
  };

  const handleToggleWakeWord = async (enable) => {
    if (enable) {
      // Require explicit consent modal
      setShowConsentModal(true);
    } else {
      try {
        await api.toggleWakeWord(false);
        onNotify('Wake-word listener disabled', 'info');
        fetchStatus();
      } catch (err) {
        onNotify('Failed to disable wake word', 'error');
      }
    }
  };

  const confirmWakeWordConsent = async () => {
    try {
      await api.toggleWakeWord(true, true);
      onNotify('Wake-word listening enabled with affirmative user consent', 'success');
      setShowConsentModal(false);
      fetchStatus();
    } catch (err) {
      onNotify('Failed to enable wake word: ' + err.message, 'error');
    }
  };

  return (
    <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Voice Controls & Speech Interface</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Natural voice interaction powered by Windows SAPI5 (TTS) and local speech recognition.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* TTS Section */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Volume2 size={18} color="var(--accent-cyan)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Text-to-Speech (SAPI5)</h2>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Speech Rate: {speechRate} WPM
            </label>
            <input
              type="range"
              min="100"
              max="250"
              value={speechRate}
              onChange={(e) => setSpeechRate(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Test Phrase
            </label>
            <textarea
              rows={3}
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              style={{ width: '100%', fontSize: '13px' }}
            />
          </div>

          <button
            onClick={handleTestSpeak}
            disabled={isSpeaking}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: 'var(--accent-cyan)',
              color: '#fff',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            <Volume2 size={15} />
            <span>{isSpeaking ? 'Speaking...' : 'Test Voice Synthesis'}</span>
          </button>
        </div>

        {/* STT Section */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Mic size={18} color="var(--accent-blue)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Speech Recognition (Microphone)</h2>
          </div>

          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Capture a voice turn from the default Windows recording device.
          </p>

          <button
            onClick={handleRecord}
            disabled={isListening}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: isListening ? 'var(--accent-rose)' : 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: '#fff',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              marginBottom: '16px',
            }}
          >
            <Mic size={15} />
            <span>{isListening ? 'Listening (5s)...' : 'Record & Transcribe'}</span>
          </button>

          {transcript && (
            <div style={{
              padding: '12px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
            }}>
              <div style={{ fontSize: '11px', color: 'var(--accent-cyan)', marginBottom: '4px' }}>
                Latest Transcript:
              </div>
              <div style={{ fontSize: '13px', color: '#fff' }}>"{transcript}"</div>
            </div>
          )}
        </div>

        {/* Wake-Word Consent Section */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Radio size={18} color="var(--accent-emerald)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Wake-Word Activation ("Nova")</h2>
          </div>

          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '16px' }}>
            NOVA strictly honors privacy by disabling background listening until explicit affirmative user consent is granted.
          </p>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            backgroundColor: 'var(--bg-primary)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: status?.wakeword_enabled ? 'var(--accent-emerald)' : 'var(--text-muted)',
              }} />
              <span style={{ fontSize: '13px', fontWeight: 500 }}>
                {status?.wakeword_enabled ? 'Wake-word Active' : 'Wake-word Inactive'}
              </span>
            </div>

            <button
              onClick={() => handleToggleWakeWord(!status?.wakeword_enabled)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                backgroundColor: status?.wakeword_enabled ? 'rgba(244, 63, 94, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                color: status?.wakeword_enabled ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                border: `1px solid ${status?.wakeword_enabled ? 'rgba(244, 63, 94, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {status?.wakeword_enabled ? 'Turn Off' : 'Enable Wake-Word'}
            </button>
          </div>
        </div>
      </div>

      {/* Explicit Affirmative Consent Modal */}
      {showConsentModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
        }}>
          <div style={{
            width: '440px',
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <ShieldAlert size={22} color="var(--accent-amber)" />
              <h3 style={{ fontSize: '16px', fontWeight: 600 }}>Enable Background Audio Listening?</h3>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '20px' }}>
              Enabling the wake-word feature allows NOVA to listen for the trigger word <strong>"Nova"</strong> in the background. Audio is processed locally and discarded immediately.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setShowConsentModal(false)}
                style={{
                  padding: '8px 14px',
                  borderRadius: '6px',
                  backgroundColor: 'var(--bg-tertiary)',
                  fontSize: '12.5px',
                  color: 'var(--text-main)',
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmWakeWordConsent}
                style={{
                  padding: '8px 14px',
                  borderRadius: '6px',
                  backgroundColor: 'var(--accent-emerald)',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  color: '#fff',
                }}
              >
                I Give Consent & Enable
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
