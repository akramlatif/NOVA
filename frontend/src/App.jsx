import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import TasksView from './components/TasksView';
import VoiceView from './components/VoiceView';
import MemoryView from './components/MemoryView';
import SystemView from './components/SystemView';
import SettingsView from './components/SettingsView';
import { api } from './api';

export default function App() {
  const [currentView, setCurrentView] = useState('chat');
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [assistantOnline, setAssistantOnline] = useState(true);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    fetchInitialData();
    const interval = setInterval(pollTelemetry, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchInitialData = async () => {
    try {
      const [convs, status, apprs] = await Promise.all([
        api.getConversations().catch(() => []),
        api.getSystemStatus().catch(() => null),
        api.getApprovals().catch(() => []),
      ]);
      setConversations(convs || []);
      if (convs && convs.length > 0) {
        setActiveConversationId(convs[0].id);
      }
      setSystemStatus(status);
      setPendingApprovals(apprs || []);
    } catch (err) {
      console.error(err);
    }
  };

  const pollTelemetry = async () => {
    try {
      const [status, apprs] = await Promise.all([
        api.getSystemStatus().catch(() => null),
        api.getApprovals().catch(() => []),
      ]);
      setSystemStatus(status);
      setPendingApprovals(apprs || []);
    } catch (err) {
      // background poll error silent
    }
  };

  const notify = (message, type = 'info') => {
    setNotification({ message, type, id: Date.now() });
    setTimeout(() => {
      setNotification((prev) => (prev?.message === message ? null : prev));
    }, 4000);
  };

  const handleResetConversation = () => {
    setActiveConversationId(null);
    setCurrentView('chat');
    notify('Started new conversation session', 'info');
  };

  const refreshConversations = async () => {
    try {
      const convs = await api.getConversations();
      setConversations(convs || []);
    } catch (err) {
      console.error(err);
    }
  };

  const getNotificationColor = (type) => {
    switch (type) {
      case 'success': return 'var(--accent-emerald)';
      case 'error': return 'var(--accent-rose)';
      case 'warning': return 'var(--accent-amber)';
      default: return 'var(--accent-cyan)';
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar Navigation */}
      <Sidebar
        currentView={currentView}
        setCurrentView={setCurrentView}
        systemStatus={systemStatus}
        pendingApprovalsCount={pendingApprovals.length}
        assistantOnline={assistantOnline}
        setAssistantOnline={setAssistantOnline}
        onResetConversation={handleResetConversation}
      />

      {/* Main View Container */}
      <main style={{ flex: 1, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {currentView === 'chat' && (
          <ChatView
            conversations={conversations}
            activeConversationId={activeConversationId}
            setActiveConversationId={setActiveConversationId}
            refreshConversations={refreshConversations}
            onNotify={notify}
          />
        )}
        {currentView === 'tasks' && <TasksView onNotify={notify} />}
        {currentView === 'voice' && <VoiceView onNotify={notify} />}
        {currentView === 'memory' && <MemoryView onNotify={notify} />}
        {currentView === 'system' && <SystemView onNotify={notify} />}
        {currentView === 'settings' && <SettingsView onNotify={notify} />}
      </main>

      {/* Notification Toast */}
      {notification && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          backgroundColor: 'var(--bg-secondary)',
          border: `1px solid ${getNotificationColor(notification.type)}`,
          boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
          borderRadius: '8px',
          padding: '12px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          zIndex: 1000,
          animation: 'fadeIn 0.2s ease',
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: getNotificationColor(notification.type),
          }} />
          <span style={{ fontSize: '13px', color: '#fff', fontWeight: 500 }}>
            {notification.message}
          </span>
        </div>
      )}
    </div>
  );
}
