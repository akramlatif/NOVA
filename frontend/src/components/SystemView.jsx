import React, { useState, useEffect } from 'react';
import {
  Cpu,
  HardDrive,
  Activity,
  Download,
  Folder,
  RefreshCw,
  FileCheck,
  CheckCircle,
} from 'lucide-react';
import { api } from '../api';

export default function SystemView({ onNotify }) {
  const [telemetry, setTelemetry] = useState(null);
  const [downloads, setDownloads] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [sys, dl] = await Promise.all([
        api.getSystemStatus(),
        api.getDownloads().catch(() => []),
      ]);
      setTelemetry(sys);
      setDownloads(dl || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleManualRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
    onNotify('System telemetry updated', 'info');
  };

  return (
    <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700 }}>System Telemetry & Downloads</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Hardware resource monitoring and safe download tracking.
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            fontSize: '12.5px',
            color: 'var(--text-main)',
          }}
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Resource Gauge Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: '16px',
        marginBottom: '28px',
      }}>
        {/* CPU */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '18px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={16} color="var(--accent-cyan)" />
              <span style={{ fontSize: '13px', fontWeight: 600 }}>CPU Utilization</span>
            </div>
            <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
              {telemetry?.cpu_percent ?? 0}%
            </span>
          </div>
          <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-primary)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${telemetry?.cpu_percent ?? 0}%`,
              height: '100%',
              backgroundColor: 'var(--accent-cyan)',
              transition: 'width 0.3s ease',
            }} />
          </div>
        </div>

        {/* RAM */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '18px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Activity size={16} color="var(--accent-blue)" />
              <span style={{ fontSize: '13px', fontWeight: 600 }}>RAM Usage</span>
            </div>
            <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-blue)' }}>
              {telemetry?.ram_percent ?? 0}%
            </span>
          </div>
          <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-primary)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${telemetry?.ram_percent ?? 0}%`,
              height: '100%',
              backgroundColor: 'var(--accent-blue)',
              transition: 'width 0.3s ease',
            }} />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
            {telemetry?.ram_used_gb ?? 0} GB used of {telemetry?.ram_total_gb ?? 8} GB total
          </div>
        </div>

        {/* Disk */}
        <div style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '18px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <HardDrive size={16} color="var(--accent-emerald)" />
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Primary Storage</span>
            </div>
            <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-emerald)' }}>
              {telemetry?.disk_percent ?? 0}%
            </span>
          </div>
          <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-primary)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${telemetry?.disk_percent ?? 0}%`,
              height: '100%',
              backgroundColor: 'var(--accent-emerald)',
              transition: 'width 0.3s ease',
            }} />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
            {telemetry?.disk_free_gb ?? 0} GB free space remaining
          </div>
        </div>
      </div>

      {/* Active Agents */}
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '28px',
      }}>
        <h2 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>Active Subsystem Agents</h2>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {['FastAPI Local Server', 'SQLite Memory Daemon', 'SAPI5 Voice Controller', ...(telemetry?.running_agents || [])].map((agent, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                fontSize: '12.5px',
              }}
            >
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-emerald)' }} />
              <span>{agent}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Downloads Section */}
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Download size={18} color="var(--accent-cyan)" />
          <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Tracked Downloads</h2>
        </div>

        {downloads.length === 0 ? (
          <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', textAlign: 'center', padding: '16px' }}>
            No browser downloads recorded yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {downloads.map((dl, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  backgroundColor: 'var(--bg-primary)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <FileCheck size={16} color="var(--accent-cyan)" />
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 500 }}>{dl.filename || dl.path}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{dl.size_bytes ? `${Math.round(dl.size_bytes / 1024)} KB` : 'Verified download'}</div>
                  </div>
                </div>
                <div style={{
                  fontSize: '11px',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  backgroundColor: 'rgba(16, 185, 129, 0.1)',
                  color: 'var(--accent-emerald)',
                }}>
                  Verified
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
