import React, { useState, useEffect } from 'react';
import {
  Play,
  XCircle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  ShieldAlert,
  Terminal,
  Activity,
  Layers,
} from 'lucide-react';
import { api } from '../api';

export default function TasksView({ onNotify }) {
  const [tasks, setTasks] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [instruction, setInstruction] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchTasksAndApprovals();
    const interval = setInterval(fetchTasksAndApprovals, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchTasksAndApprovals = async () => {
    try {
      const [tList, aList] = await Promise.all([
        api.getTasks(),
        api.getApprovals(),
      ]);
      setTasks(tList || []);
      setApprovals(aList || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    if (!instruction.trim() || submitting) return;
    setSubmitting(true);
    try {
      await api.submitTask(instruction, true);
      setInstruction('');
      onNotify('Task submitted to orchestrator', 'success');
      fetchTasksAndApprovals();
    } catch (err) {
      onNotify(err.message || 'Failed to submit task', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelTask = async (taskId) => {
    try {
      await api.cancelTask(taskId);
      onNotify('Task cancelled', 'info');
      fetchTasksAndApprovals();
    } catch (err) {
      onNotify('Failed to cancel task', 'error');
    }
  };

  const handleApprovalDecision = async (approvalId, approved) => {
    try {
      await api.decideApproval(approvalId, approved);
      onNotify(approved ? 'Action approved' : 'Action rejected', approved ? 'success' : 'warning');
      fetchTasksAndApprovals();
    } catch (err) {
      onNotify('Failed to submit approval decision', 'error');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'var(--accent-emerald)';
      case 'running': return 'var(--accent-cyan)';
      case 'planning': return 'var(--accent-blue)';
      case 'failed': return 'var(--accent-rose)';
      case 'cancelled': return 'var(--text-muted)';
      default: return 'var(--accent-amber)';
    }
  };

  return (
    <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Task Orchestration & Agent Activity</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Deconstruct multi-step computer tasks into executable tool plans with human-in-the-loop safety.
        </p>
      </div>

      {/* Task Input Box */}
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '28px',
      }}>
        <form onSubmit={handleCreateTask}>
          <label style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
            Instruct NOVA to Execute a Goal
          </label>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder='e.g., "Open python website and check download options" or "Create a project folder"'
              style={{ flex: 1, fontSize: '13px' }}
            />
            <button
              type="submit"
              disabled={!instruction.trim() || submitting}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '8px',
                backgroundColor: 'var(--accent-cyan)',
                color: '#fff',
                fontWeight: 600,
                fontSize: '13px',
              }}
            >
              <Play size={15} />
              <span>{submitting ? 'Planning...' : 'Run Task'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Pending Approvals Section */}
      {approvals.length > 0 && (
        <div style={{ marginBottom: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <ShieldAlert size={18} color="var(--accent-rose)" />
            <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#fca5a5' }}>
              Pending Human Confirmations ({approvals.length})
            </h2>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {approvals.map((appr) => (
              <div
                key={appr.id}
                style={{
                  backgroundColor: 'rgba(244, 63, 94, 0.08)',
                  border: '1px solid rgba(244, 63, 94, 0.3)',
                  borderRadius: '10px',
                  padding: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#fff' }}>
                    {appr.description}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Action Type: <code style={{ color: 'var(--accent-cyan)' }}>{appr.action_type}</code>
                  </div>
                  {Object.keys(appr.payload || {}).length > 0 && (
                    <div style={{
                      marginTop: '8px',
                      fontSize: '11.5px',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--text-muted)',
                      backgroundColor: 'rgba(0,0,0,0.2)',
                      padding: '4px 8px',
                      borderRadius: '4px',
                    }}>
                      {JSON.stringify(appr.payload)}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleApprovalDecision(appr.id, true)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 14px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--accent-emerald)',
                      color: '#fff',
                      fontSize: '12px',
                      fontWeight: 600,
                    }}
                  >
                    <CheckCircle2 size={14} />
                    <span>Approve</span>
                  </button>
                  <button
                    onClick={() => handleApprovalDecision(appr.id, false)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 14px',
                      borderRadius: '6px',
                      backgroundColor: 'rgba(51, 65, 85, 0.6)',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                  >
                    <XCircle size={14} />
                    <span>Reject</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Task List */}
      <div>
        <h2 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
          Recent & Active Tasks ({tasks.length})
        </h2>

        {tasks.length === 0 ? (
          <div style={{
            padding: '32px',
            textAlign: 'center',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '10px',
            border: '1px solid var(--border-color)',
            color: 'var(--text-muted)',
            fontSize: '13px',
          }}>
            No tasks submitted yet. Enter a goal above to start!
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {tasks.map((task) => (
              <div
                key={task.task_id}
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px 20px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(255,255,255,0.06)',
                      color: getStatusColor(task.status),
                      border: `1px solid ${getStatusColor(task.status)}`,
                    }}>
                      {task.status}
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: 600 }}>{task.instruction}</div>
                  </div>

                  {['queued', 'planning', 'running'].includes(task.status) && (
                    <button
                      onClick={() => handleCancelTask(task.task_id)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        backgroundColor: 'rgba(244, 63, 94, 0.1)',
                        color: 'var(--accent-rose)',
                        fontSize: '12px',
                        border: '1px solid rgba(244, 63, 94, 0.3)',
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>

                {/* Steps List */}
                {task.steps?.length > 0 && (
                  <div style={{
                    marginTop: '12px',
                    paddingTop: '10px',
                    borderTop: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}>
                    {task.steps.map((s, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          fontSize: '12px',
                          color: 'var(--text-muted)',
                        }}
                      >
                        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                          Step {idx + 1}
                        </span>
                        <span>{s.description || s.action}</span>
                      </div>
                    ))}
                  </div>
                )}

                {task.result && (
                  <div style={{
                    marginTop: '10px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    fontSize: '12px',
                    color: '#6ee7b7',
                  }}>
                    Result: {task.result}
                  </div>
                )}

                {task.error && (
                  <div style={{
                    marginTop: '10px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(244, 63, 94, 0.08)',
                    border: '1px solid rgba(244, 63, 94, 0.25)',
                    fontSize: '12px',
                    color: '#fca5a5',
                  }}>
                    Error: {task.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
