import React, { useState, useEffect } from 'react';
import {
  Laptop,
  Smartphone,
  Key,
  Send,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  RefreshCw,
  QrCode,
  Lock,
  Unlock,
  Radio,
  FileDown,
} from 'lucide-react';
import { api, setAuthToken, getAuthToken } from '../api';

export default function RemoteView({ onNotify }) {
  const [devices, setDevices] = useState([]);
  const [pairingCode, setPairingCode] = useState(null);
  const [inputCode, setInputCode] = useState('');
  const [remoteCommand, setRemoteCommand] = useState('');
  const [selectedDevice, setSelectedDevice] = useState('local-agent-win11');
  const [dispatching, setDispatching] = useState(false);
  const [lastDispatchedTask, setLastDispatchedTask] = useState(null);

  // Auth State
  const [currentUser, setCurrentUser] = useState(null);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('nova1234');
  const [authLoading, setAuthLoading] = useState(false);

  useEffect(() => {
    fetchDevices();
    checkCurrentUser();
    const interval = setInterval(fetchDevices, 4000);
    return () => clearInterval(interval);
  }, []);

  const fetchDevices = async () => {
    try {
      const list = await api.getDevices();
      setDevices(list || []);
    } catch (err) {
      console.error(err);
    }
  };

  const checkCurrentUser = async () => {
    const token = getAuthToken();
    if (!token) return;
    try {
      const user = await api.getMe();
      setCurrentUser(user);
    } catch {
      setAuthToken(null);
      setCurrentUser(null);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      const res = await api.login(username, password);
      setAuthToken(res.access_token);
      setCurrentUser({ username: res.username });
      onNotify(`Logged in as ${res.username}`, 'success');
    } catch (err) {
      onNotify(err.message || 'Login failed', 'error');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setAuthToken(null);
    setCurrentUser(null);
    onNotify('Logged out from dashboard', 'info');
  };

  const handleRequestPairingCode = async () => {
    try {
      const res = await api.requestPairingCode();
      setPairingCode(res.code);
      onNotify(`Generated pairing code: ${res.code}`, 'success');
    } catch (err) {
      onNotify('Failed to generate pairing code', 'error');
    }
  };

  const handleConfirmPairing = async (e) => {
    e.preventDefault();
    if (!inputCode.trim()) return;
    try {
      const res = await api.confirmPairing(inputCode);
      setAuthToken(res.access_token);
      setInputCode('');
      onNotify(`Paired successfully with ${res.device_name}!`, 'success');
      fetchDevices();
      checkCurrentUser();
    } catch (err) {
      onNotify(err.message || 'Pairing failed. Check code.', 'error');
    }
  };

  const handleSendRemoteTask = async (e) => {
    e.preventDefault();
    if (!remoteCommand.trim() || dispatching) return;
    setDispatching(true);
    try {
      const res = await api.sendRemoteTask(selectedDevice, remoteCommand);
      setLastDispatchedTask(res);
      setRemoteCommand('');
      onNotify('Remote task forwarded to paired Windows PC', 'success');
    } catch (err) {
      onNotify(err.message || 'Remote dispatch failed (Check login or device online status)', 'error');
    } finally {
      setDispatching(false);
    }
  };

  return (
    <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Web Dashboard & Secure Remote Access</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Forward remote instructions from phones or secondary browsers to your paired Windows PC.
          </p>
        </div>

        {/* User Session Pill */}
        <div>
          {currentUser ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>
                Authenticated as <strong style={{ color: '#fff' }}>{currentUser.username}</strong>
              </div>
              <button
                onClick={handleLogout}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(244, 63, 94, 0.15)',
                  border: '1px solid rgba(244, 63, 94, 0.3)',
                  color: 'var(--accent-rose)',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              >
                Logout
              </button>
            </div>
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Lock size={14} />
              <span>Dashboard is locked. Login below to execute remote tasks.</span>
            </div>
          )}
        </div>
      </div>

      {/* Login Card if not authenticated */}
      {!currentUser && (
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--accent-cyan)',
          borderRadius: '12px',
          padding: '20px',
          marginBottom: '24px',
          maxWidth: '540px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Lock size={18} color="var(--accent-cyan)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Authenticate Web Session</h2>
          </div>
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                style={{ width: '100%', fontSize: '13px' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ width: '100%', fontSize: '13px' }}
              />
            </div>
            <button
              type="submit"
              disabled={authLoading}
              style={{
                padding: '10px',
                borderRadius: '8px',
                backgroundColor: 'var(--accent-cyan)',
                color: '#fff',
                fontSize: '13px',
                fontWeight: 600,
              }}
            >
              {authLoading ? 'Verifying...' : 'Sign In & Unlock Remote Execution'}
            </button>
          </form>
        </div>
      )}

      {/* Remote Task Forwarder */}
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '28px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Radio size={18} color="var(--accent-emerald)" />
          <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Remote Task Dispatcher</h2>
        </div>

        <form onSubmit={handleSendRemoteTask}>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '12px' }}>
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              style={{ width: '220px', fontSize: '13px' }}
            >
              {devices.map((d) => (
                <option key={d.device_id} value={d.device_id}>
                  {d.device_name} ({d.status})
                </option>
              ))}
            </select>

            <input
              type="text"
              value={remoteCommand}
              onChange={(e) => setRemoteCommand(e.target.value)}
              placeholder='e.g., "Download this PDF to my laptop" or "Check CPU usage"'
              disabled={!currentUser}
              style={{ flex: 1, fontSize: '13px' }}
            />

            <button
              type="submit"
              disabled={!remoteCommand.trim() || dispatching || !currentUser}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '8px',
                backgroundColor: 'var(--accent-emerald)',
                color: '#fff',
                fontWeight: 600,
                fontSize: '13px',
              }}
            >
              <Send size={15} />
              <span>{dispatching ? 'Forwarding...' : 'Dispatch Task'}</span>
            </button>
          </div>
        </form>

        {/* Quick Examples */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>Quick Examples:</span>
          {[
            'Download the official Python tutorial PDF to my laptop',
            'Organize downloaded files by type',
            'Check system memory and running agents',
          ].map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => setRemoteCommand(prompt)}
              style={{
                fontSize: '11.5px',
                padding: '4px 10px',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                color: 'var(--text-main)',
              }}
            >
              {prompt}
            </button>
          ))}
        </div>

        {lastDispatchedTask && (
          <div style={{
            marginTop: '16px',
            padding: '12px 14px',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '8px',
            fontSize: '12.5px',
          }}>
            <div style={{ color: 'var(--accent-emerald)', fontWeight: 600, marginBottom: '2px' }}>
              ✓ Task Dispatched to Paired Windows Agent
            </div>
            <div style={{ color: 'var(--text-muted)' }}>
              Task ID: <code style={{ color: '#fff' }}>{lastDispatchedTask.task_id}</code> • Status: {lastDispatchedTask.status}
            </div>
          </div>
        )}
      </div>

      {/* Device Pairing Section (Two Columns) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        {/* Generate Code on PC */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Laptop size={18} color="var(--accent-cyan)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Pair This Windows Computer</h2>
          </div>
          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '16px' }}>
            Generate a secure, single-use 5-minute pairing code to connect your phone or remote web dashboard.
          </p>

          <button
            onClick={handleRequestPairingCode}
            style={{
              padding: '8px 16px',
              backgroundColor: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              color: '#fff',
            }}
          >
            Generate Pairing Code
          </button>

          {pairingCode && (
            <div style={{
              marginTop: '16px',
              padding: '16px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: '8px',
              border: '1px solid var(--accent-cyan)',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Your Pairing Code (Valid 5 mins)
              </div>
              <div style={{
                fontSize: '26px',
                fontWeight: 800,
                letterSpacing: '0.15em',
                color: 'var(--accent-cyan)',
                margin: '8px 0',
                fontFamily: 'var(--font-mono)',
              }}>
                {pairingCode}
              </div>
              <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                Enter this code on your mobile dashboard to establish secure pairing.
              </div>
            </div>
          )}
        </div>

        {/* Enter Code on Remote Device */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Smartphone size={18} color="var(--accent-blue)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Pair Remote Device / Phone</h2>
          </div>
          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '16px' }}>
            If you are accessing this dashboard from another device, enter the code shown on your laptop.
          </p>

          <form onSubmit={handleConfirmPairing} style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value.toUpperCase())}
              placeholder="e.g. NOVA-7829"
              style={{
                flex: 1,
                fontSize: '13.5px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                fontFamily: 'var(--font-mono)',
              }}
            />
            <button
              type="submit"
              disabled={!inputCode.trim()}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                backgroundColor: 'var(--accent-blue)',
                color: '#fff',
                fontSize: '13px',
                fontWeight: 600,
              }}
            >
              Pair
            </button>
          </form>
        </div>
      </div>

      {/* Paired Devices List */}
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={18} color="var(--accent-emerald)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Paired Devices & Presence ({devices.length})</h2>
          </div>
          <button
            onClick={fetchDevices}
            style={{ padding: '4px 8px', color: 'var(--text-muted)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <RefreshCw size={12} />
            <span>Refresh</span>
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {devices.map((d) => (
            <div
              key={d.device_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Laptop size={18} color="var(--accent-cyan)" />
                <div>
                  <div style={{ fontSize: '13.5px', fontWeight: 600 }}>{d.device_name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    OS: {d.os} • Last seen: {d.last_seen_seconds_ago}s ago
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: d.status === 'online' ? 'var(--accent-emerald)' : 'var(--text-muted)',
                }} />
                <span style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: d.status === 'online' ? 'var(--accent-emerald)' : 'var(--text-muted)',
                  textTransform: 'capitalize',
                }}>
                  {d.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
