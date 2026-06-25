/**
 * WorkflowTimeline — 7-step visual delivery progress tracker.
 *
 * Maps the robot delivery workflow from request submission to
 * return-to-base. Used in both QuickRequest (mobile) and
 * AdminDashboard (desktop).
 *
 * Props:
 *   deliveryStatus  – Backend delivery status string
 *   robotState      – Current RobotState value from WebSocket telemetry
 *   compact         – Compact mode for admin table cells (default: false)
 *   arrivedAt       – Optional ISO timestamp when robot arrived
 *   showLabels      – Show step description labels (default: true)
 */

import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, Circle, Loader } from 'lucide-react';
import { RobotState, deliveryStatusToStep } from '../lib/robotStateLibrary';

export interface WorkflowStep {
  label: string;
  sublabel: string;
  emoji: string;
  color: string;
}

export const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    label:    'Request Submitted',
    sublabel: 'Delivery queued on server',
    emoji:    '📥',
    color:    '#06b6d4',
  },
  {
    label:    'Validating & Assigning',
    sublabel: 'Checking inventory & robot readiness',
    emoji:    '🔍',
    color:    '#8b5cf6',
  },
  {
    label:    'Robot Navigating',
    sublabel: 'On the way to your location',
    emoji:    '🚀',
    color:    '#2563eb',
  },
  {
    label:    'Arrived at Destination',
    sublabel: 'Robot is at your workbench',
    emoji:    '📍',
    color:    '#10b981',
  },
  {
    label:    'Panel Open',
    sublabel: 'Collect your equipment now',
    emoji:    '🔓',
    color:    '#06b6d4',
  },
  {
    label:    'Pickup Confirmed',
    sublabel: 'Item collected — panel closing',
    emoji:    '✅',
    color:    '#10b981',
  },
  {
    label:    'Returned to Base',
    sublabel: 'Robot back at docking station',
    emoji:    '🏠',
    color:    '#2563eb',
  },
];

interface WorkflowTimelineProps {
  deliveryStatus: string;
  robotState: RobotState;
  compact?: boolean;
  showLabels?: boolean;
  arrivedAt?: string | null;
}

export const WorkflowTimeline: React.FC<WorkflowTimelineProps> = ({
  deliveryStatus,
  robotState,
  compact = false,
  showLabels = true,
  arrivedAt,
}) => {
  const currentStep = deliveryStatusToStep(deliveryStatus, robotState);
  const isCancelled = deliveryStatus === 'cancelled';
  const isFailed = deliveryStatus === 'failed' || robotState === RobotState.TASK_FAILED;

  // ── Compact horizontal pill mode (for admin tables) ──────
  if (compact) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {WORKFLOW_STEPS.map((step, idx) => {
          const isDone   = idx <= currentStep;
          const isActive = idx === currentStep;
          return (
            <div
              key={idx}
              title={step.label}
              style={{
                width:        isActive ? '20px' : '10px',
                height:       '6px',
                borderRadius: '3px',
                background:   isCancelled ? 'rgba(255,255,255,0.1)' :
                              isFailed    ? 'rgba(244,63,94,0.4)' :
                              isDone      ? step.color : 'rgba(255,255,255,0.08)',
                transition:   'all 0.3s ease',
                boxShadow:    isActive && !isCancelled && !isFailed
                              ? `0 0 6px ${step.color}` : 'none',
              }}
            />
          );
        })}
        <span style={{
          fontSize: '0.7rem',
          color: isCancelled ? 'var(--accent-red)' :
                 isFailed ? 'var(--accent-red)' :
                 currentStep >= 6 ? 'var(--accent-green)' : 'var(--text-secondary)',
          marginLeft: '4px',
          fontWeight: 600,
        }}>
          {isCancelled ? 'Cancelled' :
           isFailed ? 'Failed' :
           currentStep >= 6 ? 'Done' :
           `Step ${currentStep + 1}/7`}
        </span>
      </div>
    );
  }

  // ── Full vertical timeline mode (for user mobile view) ───
  return (
    <div style={{
      display:        'flex',
      flexDirection:  'column',
      gap:            '0',
      position:       'relative',
      paddingLeft:    '36px',
    }}>
      {/* Vertical connector line */}
      <div style={{
        position:   'absolute',
        left:       '11px',
        top:        '12px',
        bottom:     '12px',
        width:      '2px',
        background: 'rgba(255,255,255,0.06)',
      }} />

      {/* Filled progress line */}
      <motion.div
        style={{
          position:   'absolute',
          left:       '11px',
          top:        '12px',
          width:      '2px',
          background: isCancelled ? 'var(--accent-red)' :
                      isFailed    ? 'var(--accent-red)' :
                      'linear-gradient(to bottom, #06b6d4, #10b981)',
          originY:    0,
        }}
        initial={{ height: '0%' }}
        animate={{
          height: isCancelled || isFailed ? '8%' :
                  `${Math.max(0, (currentStep / (WORKFLOW_STEPS.length - 1)) * 100)}%`
        }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />

      {WORKFLOW_STEPS.map((step, idx) => {
        const isDone   = idx <  currentStep && !isCancelled && !isFailed;
        const isActive = idx === currentStep && !isCancelled && !isFailed;
        const isPending = idx > currentStep || isCancelled || isFailed;

        const dotColor = isCancelled || isFailed ? 'rgba(255,255,255,0.1)' :
                         isDone   ? step.color :
                         isActive ? step.color : 'rgba(255,255,255,0.1)';

        // Time label for arrived step
        const timeLabel = idx === 3 && arrivedAt
          ? new Date(arrivedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : null;

        return (
          <div
            key={idx}
            style={{
              position:   'relative',
              paddingBottom: idx < WORKFLOW_STEPS.length - 1 ? '20px' : '0',
              opacity:    isPending ? 0.45 : 1,
              transition: 'opacity 0.3s ease',
            }}
          >
            {/* Step dot */}
            <div style={{
              position:        'absolute',
              left:            '-29px',
              top:             '2px',
              width:           '22px',
              height:          '22px',
              borderRadius:    '50%',
              background:      isDone ? dotColor : isActive ? 'transparent' : 'rgba(255,255,255,0.05)',
              border:          isActive ? `2px solid ${step.color}` :
                               isDone   ? 'none' : '2px solid rgba(255,255,255,0.1)',
              boxShadow:       isActive ? `0 0 12px ${step.color}` : 'none',
              display:         'flex',
              alignItems:      'center',
              justifyContent:  'center',
              transition:      'all 0.4s ease',
            }}>
              {isDone ? (
                <CheckCircle size={14} color="#fff" />
              ) : isActive ? (
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 1.2 }}
                  style={{
                    width:        '10px',
                    height:       '10px',
                    borderRadius: '50%',
                    background:   step.color,
                    boxShadow:    `0 0 8px ${step.color}`,
                  }}
                />
              ) : (
                <Circle size={10} color="rgba(255,255,255,0.2)" />
              )}
            </div>

            {/* Step content */}
            <div>
              <div style={{
                display:    'flex',
                alignItems: 'center',
                gap:        '6px',
                marginBottom: '2px',
              }}>
                <span style={{ fontSize: '0.8rem' }}>{step.emoji}</span>
                <span style={{
                  fontWeight: isActive || isDone ? 700 : 500,
                  color:      isActive ? step.color : isDone ? '#fff' : 'var(--text-secondary)',
                  fontSize:   '0.9rem',
                  transition: 'color 0.3s',
                }}>
                  {step.label}
                </span>
                {isActive && (
                  <motion.div
                    animate={{ opacity: [1, 0.4, 1] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  >
                    <Loader size={12} color={step.color} style={{ animation: 'spin 1s linear infinite' }} />
                  </motion.div>
                )}
                {timeLabel && (
                  <span style={{
                    fontSize:   '0.7rem',
                    color:      'var(--accent-cyan)',
                    fontFamily: 'var(--font-mono)',
                    marginLeft: '4px',
                  }}>
                    @ {timeLabel}
                  </span>
                )}
              </div>
              {showLabels && (
                <div style={{
                  fontSize: '0.75rem',
                  color:    'var(--text-secondary)',
                }}>
                  {step.sublabel}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default WorkflowTimeline;
