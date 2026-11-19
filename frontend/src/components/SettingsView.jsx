import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Server,
  Database,
  Folder,
  Volume2,
  Check,
} from 'lucide-react';
import { api } from '../api';

export default function SettingsView({ onNotify }) {
  const [settings, setSettings] = useState(null);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
      if (data) setMemoryEnabled(data.memory_enabled);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.updateSettings({ memory_enabled: memoryEnabled });
      onNotify('Settings saved successfully', 'success');
      fetchSettings();
    } catch (err) {
      onNotify('Failed to update settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 700 }}>System Configuration & Preferences</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Configure runtime environments, AI model backend, and persistent memory retention.
        </p>
      </div>

      <form onSubmit={handleSave} style={{ maxWidth: '640px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* LLM Backend */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Server size={18} color="var(--accent-cyan)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Ollama AI Engine</h2>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Host Endpoint (Localhost only)
            </label>
            <input
              type="text"
              readOnly
              value={settings?.ollama_url || 'http://127.0.0.1:11434'}
              style={{ width: '100%', fontSize: '13px', opacity: 0.8 }}
            />
          </div>

          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Active Model
            </label>
            <input
              type="text"
              readOnly
              value={settings?.model_name || 'qwen2.5:3b'}
              style={{ width: '100%', fontSize: '13px', opacity: 0.8 }}
            />
          </div>
        </div>

        {/* Storage Paths */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Folder size={18} color="var(--accent-blue)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Storage Paths</h2>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Data Directory
            </label>
            <input
              type="text"
              readOnly
              value={settings?.data_dir || 'D:/NOVA/data'}
              style={{ width: '100%', fontSize: '13px', opacity: 0.8 }}
            />
          </div>

          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Safe Downloads Directory
            </label>
            <input
              type="text"
              readOnly
              value={settings?.download_dir || 'D:/NOVA/data/downloads'}
              style={{ width: '100%', fontSize: '13px', opacity: 0.8 }}
            />
          </div>
        </div>

        {/* Memory Retention Toggle */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Database size={18} color="var(--accent-emerald)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Memory System</h2>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '13.5px', fontWeight: 600 }}>Enable Persistent Memory</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Store user preferences and context across sessions.
              </div>
            </div>

            <button
              type="button"
              onClick={() => setMemoryEnabled(!memoryEnabled)}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                backgroundColor: memoryEnabled ? 'var(--accent-emerald)' : 'var(--bg-tertiary)',
                color: '#fff',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {memoryEnabled ? 'Enabled' : 'Disabled'}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '12px',
            borderRadius: '8px',
            backgroundColor: 'var(--accent-cyan)',
            color: '#fff',
            fontSize: '13.5px',
            fontWeight: 600,
          }}
        >
          <Check size={16} />
          <span>{saving ? 'Saving...' : 'Save Configuration'}</span>
        </button>
      </form>
    </div>
  );
}
