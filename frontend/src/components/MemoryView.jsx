import React, { useState, useEffect } from 'react';
import {
  Database,
  Search,
  Plus,
  Trash2,
  Tag,
  Sliders,
  Check,
} from 'lucide-react';
import { api } from '../api';

export default function MemoryView({ onNotify }) {
  const [memories, setMemories] = useState([]);
  const [preferences, setPreferences] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  // New Memory Form
  const [newKey, setNewKey] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newCat, setNewCat] = useState('fact');

  // New Preference Form
  const [prefKey, setPrefKey] = useState('');
  const [prefVal, setPrefVal] = useState('');

  const categories = [
    { id: '', label: 'All Categories' },
    { id: 'fact', label: 'Facts' },
    { id: 'preference', label: 'Preferences' },
    { id: 'project', label: 'Projects' },
    { id: 'application', label: 'Applications' },
    { id: 'task', label: 'Task Outcomes' },
  ];

  useEffect(() => {
    fetchMemories();
    fetchPreferences();
  }, [searchQuery, selectedCategory]);

  const fetchMemories = async () => {
    try {
      const data = await api.getMemories(searchQuery, selectedCategory);
      setMemories(data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPreferences = async () => {
    try {
      const data = await api.getPreferences();
      setPreferences(data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddMemory = async (e) => {
    e.preventDefault();
    if (!newKey.trim() || !newContent.trim()) return;
    try {
      await api.addMemory(newKey, newContent, newCat);
      onNotify(`Memory "${newKey}" stored`, 'success');
      setNewKey('');
      setNewContent('');
      setShowAddModal(false);
      fetchMemories();
    } catch (err) {
      onNotify(err.message || 'Failed to save memory', 'error');
    }
  };

  const handleDeleteMemory = async (key) => {
    try {
      await api.deleteMemory(key);
      onNotify(`Forgot memory "${key}"`, 'info');
      fetchMemories();
    } catch (err) {
      onNotify('Failed to delete memory', 'error');
    }
  };

  const handleSavePreference = async (e) => {
    e.preventDefault();
    if (!prefKey.trim() || !prefVal.trim()) return;
    try {
      await api.setPreference(prefKey, prefVal, 'ui');
      onNotify(`Preference "${prefKey}" saved`, 'success');
      setPrefKey('');
      setPrefVal('');
      fetchPreferences();
    } catch (err) {
      onNotify('Failed to save preference', 'error');
    }
  };

  return (
    <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Persistent Memory & User Preferences</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            SQLite-backed episodic memory with privacy sanitization blocking passwords and secret keys.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 14px',
            backgroundColor: 'var(--accent-cyan)',
            color: '#fff',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          <Plus size={15} />
          <span>Add Memory</span>
        </button>
      </div>

      {/* Search & Category Filter Bar */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '12px',
        alignItems: 'center',
        marginBottom: '20px',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '6px 12px',
          flex: 1,
          minWidth: '220px',
        }}>
          <Search size={15} color="var(--text-muted)" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memories by keyword..."
            style={{ border: 'none', background: 'transparent', flex: 1, fontSize: '13px' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {categories.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedCategory(c.id)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                backgroundColor: selectedCategory === c.id ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
                border: `1px solid ${selectedCategory === c.id ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                color: selectedCategory === c.id ? 'var(--accent-cyan)' : 'var(--text-muted)',
              }}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Memories Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: '14px',
        marginBottom: '32px',
      }}>
        {memories.length === 0 ? (
          <div style={{
            gridColumn: '1 / -1',
            padding: '32px',
            textAlign: 'center',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '10px',
            border: '1px solid var(--border-color)',
            color: 'var(--text-muted)',
            fontSize: '13px',
          }}>
            No memories found matching your criteria.
          </div>
        ) : (
          memories.map((m, idx) => (
            <div
              key={m.id || idx}
              style={{
                backgroundColor: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{
                    fontSize: '10.5px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    color: 'var(--accent-cyan)',
                  }}>
                    {m.category}
                  </span>
                  <button
                    onClick={() => handleDeleteMemory(m.key)}
                    title="Forget memory"
                    style={{ padding: '4px', color: 'var(--text-muted)' }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                <div style={{ fontSize: '13.5px', fontWeight: 600, marginBottom: '6px' }}>{m.key}</div>
                <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', lineHeight: 1.5 }}>{m.content}</div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* User Preferences Section */}
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Sliders size={18} color="var(--accent-blue)" />
          <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Saved User Preferences</h2>
        </div>

        <form onSubmit={handleSavePreference} style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
          <input
            type="text"
            value={prefKey}
            onChange={(e) => setPrefKey(e.target.value)}
            placeholder="Preference Key (e.g. editor)"
            style={{ flex: 1, fontSize: '12.5px' }}
          />
          <input
            type="text"
            value={prefVal}
            onChange={(e) => setPrefVal(e.target.value)}
            placeholder="Value (e.g. VS Code)"
            style={{ flex: 1, fontSize: '12.5px' }}
          />
          <button
            type="submit"
            style={{
              padding: '8px 14px',
              backgroundColor: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: '#fff',
              borderRadius: '6px',
              fontSize: '12.5px',
              fontWeight: 500,
            }}
          >
            Save
          </button>
        </form>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {preferences.length === 0 ? (
            <div style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>No preferences saved yet.</div>
          ) : (
            preferences.map((p, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'var(--bg-primary)',
                  border: '1px solid var(--border-subtle)',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              >
                <span style={{ color: 'var(--text-muted)' }}>{p.key}:</span>
                <span style={{ color: '#fff', fontWeight: 500 }}>{p.value}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Add Memory Modal */}
      {showAddModal && (
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
            width: '420px',
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            padding: '24px',
          }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>Store New Memory</h3>
            <form onSubmit={handleAddMemory} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Category
                </label>
                <select
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value)}
                  style={{ width: '100%', fontSize: '13px' }}
                >
                  <option value="fact">Fact</option>
                  <option value="preference">Preference</option>
                  <option value="project">Project</option>
                  <option value="application">Application</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Key / Identifier
                </label>
                <input
                  type="text"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="e.g. main_workspace"
                  style={{ width: '100%', fontSize: '13px' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Content / Value
                </label>
                <textarea
                  rows={3}
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="e.g. D:/Projects/NOVA"
                  style={{ width: '100%', fontSize: '13px' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    backgroundColor: 'var(--bg-tertiary)',
                    fontSize: '12.5px',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    backgroundColor: 'var(--accent-cyan)',
                    fontWeight: 600,
                    fontSize: '12.5px',
                    color: '#fff',
                  }}
                >
                  Save Memory
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
