import React from 'react';
import {
  MessageSquare,
  CheckSquare,
  Mic,
  Database,
  Cpu,
  Settings,
  ShieldAlert,
  Power,
  RotateCcw,
} from 'lucide-react';

export default function Sidebar({
  currentView,
  setCurrentView,
  systemStatus,
  pendingApprovalsCount,
  assistantOnline,
  setAssistantOnline,
  onResetConversation,
}) {
  const navItems = [
    { id: 'chat', label: 'Chat & Assist', icon: MessageSquare },
    {
      id: 'tasks',
      label: 'Tasks & Activity',
      icon: CheckSquare,
      badge: systemStatus?.active_tasks > 0 ? `${systemStatus.active_tasks} active` : null,
      badgeColor: 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30',
    },
    { id: 'voice', label: 'Voice Controls', icon: Mic },
    { id: 'memory', label: 'Memory System', icon: Database },
    { id: 'system', label: 'System & Downloads', icon: Cpu },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside style={{
      width: '260px',
      backgroundColor: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border-subtle)',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      flexShrink: 0,
    }}>
      {/* Brand Header */}
      <div style={{
        padding: '20px 18px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(6, 182, 212, 0.35)',
            fontWeight: 800,
            fontSize: '15px',
            color: '#fff',
          }}>
            N
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '15px', letterSpacing: '0.04em' }}>NOVA</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Local Computer Agent</div>
          </div>
        </div>
        <span style={{
          fontSize: '10px',
          padding: '2px 6px',
          borderRadius: '4px',
          background: 'rgba(51, 65, 85, 0.6)',
          color: 'var(--text-muted)',
          border: '1px solid var(--border-color)',
        }}>v1.0</span>
      </div>

      {/* Approvals Alert Bar (if pending) */}
      {pendingApprovalsCount > 0 && (
        <div
          onClick={() => setCurrentView('tasks')}
          style={{
            margin: '12px 14px 4px 14px',
            padding: '10px 12px',
            borderRadius: '8px',
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.4)',
            color: '#fca5a5',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: 600,
          }}
        >
          <ShieldAlert size={16} color="#f43f5e" />
          <span>{pendingApprovalsCount} Action{pendingApprovalsCount > 1 ? 's' : ''} Need Approval</span>
        </div>
      )}

      {/* Nav List */}
      <nav style={{ padding: '14px 10px', flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentView(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 12px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? '#fff' : 'var(--text-muted)',
                backgroundColor: isActive ? 'var(--bg-tertiary)' : 'transparent',
                borderLeft: isActive ? '3px solid var(--accent-cyan)' : '3px solid transparent',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <Icon size={18} color={isActive ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && (
                <span style={{
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(6, 182, 212, 0.2)',
                  color: 'var(--accent-cyan)',
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                }}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer System Controls */}
      <div style={{
        padding: '14px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}>
        {/* Assistant Status Card */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          background: 'var(--bg-primary)',
          borderRadius: '8px',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: assistantOnline ? 'var(--accent-emerald)' : 'var(--accent-amber)',
              boxShadow: assistantOnline ? '0 0 8px #10b981' : 'none',
            }} />
            <span style={{ fontSize: '12px', fontWeight: 500 }}>
              {assistantOnline ? 'Assistant Ready' : 'Assistant Paused'}
            </span>
          </div>

          <button
            onClick={() => setAssistantOnline(!assistantOnline)}
            title={assistantOnline ? "Pause Assistant" : "Resume Assistant"}
            style={{
              padding: '4px',
              borderRadius: '4px',
              color: assistantOnline ? 'var(--accent-emerald)' : 'var(--text-muted)',
            }}
          >
            <Power size={14} />
          </button>
        </div>

        {/* Quick New Conversation Button */}
        <button
          onClick={onResetConversation}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '8px 12px',
            backgroundColor: 'var(--bg-tertiary)',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-main)',
          }}
        >
          <RotateCcw size={13} />
          <span>New Conversation</span>
        </button>
      </div>
    </aside>
  );
}
